"""Audit Stage 2 source counts and Stage 3 source-wise held-out accuracy.

Run from the repository root with .venv-ml. This is read-only with respect to
the database and input CSVs; it writes only its JSON report.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import f1_score
from transformers import AutoModelForSequenceClassification, AutoTokenizer

BASE = Path(__file__).resolve().parents[2]
SRC = BASE / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(BASE / "scripts" / "03_bert_training"))

import build_training_dataset as builder  # noqa: E402
from db.models import Company, Fact, Filing  # noqa: E402
from db.session import get_session  # noqa: E402

SPLIT_DIR = BASE / "data" / "training_company_split"
MODEL_PATH = BASE / "data" / "models" / "brsr_company_split_classifier" / "seed_99" / "best_model"
REPORT_PATH = BASE / "results" / "audit" / "stage2_sourcewise_results.json"
SOURCE_ORDER = ("section_b", "section_c", "notes_principle")
BOOTSTRAP_REPS = 2000
BOOTSTRAP_SEED = 42
INFERENCE_BATCH_SIZE = 8
HISTORICAL_SECTION_B_REFERENCE = 17219  # user-reported earlier count; its generating query is not present in this repo


def collect_filter_diagnostics() -> dict:
    """Recount the current DB through the exact builder selection/filter path."""
    counts = Counter()
    clean_labeled: dict[tuple[int, str, str], dict[int, str]] = defaultdict(dict)
    with get_session() as session:
        companies = session.query(Company).all()
        for company in companies:
            filings = session.query(Filing).filter_by(company_id=company.id).all()
            for filing in filings:
                facts = session.query(Fact).filter(Fact.filing_id == filing.id).all()
                for fact in facts:
                    dim = (fact.dimensions or {}).get("PrincipleAxis")
                    has_axis = dim in builder.PRINCIPLE_TO_LABEL
                    if has_axis:
                        counts["raw_valid_principle_axis_facts_all_concepts"] += 1

                    if "ExplanatoryTextBlock" not in (fact.concept or ""):
                        continue
                    counts["explanatory_text_facts"] += 1
                    if has_axis:
                        counts["section_b_explanatory_facts"] += 1
                    if not fact.value or not fact.value.strip():
                        counts["empty_explanatory_facts"] += 1
                        continue

                    raw_text = fact.value.strip()
                    if not builder.is_clean_narrative(raw_text):
                        counts["noise_filtered_explanatory_facts"] += 1
                        if has_axis:
                            counts["section_b_noise_filtered"] += 1
                        continue

                    counts["clean_explanatory_facts"] += 1
                    if has_axis:
                        counts["section_b_clean_candidates"] += 1
                    clean_text = builder.URL_PATTERN.sub("", raw_text).strip()
                    clean_text = re.sub(r"\s+", " ", clean_text).strip()

                    if has_axis:
                        label = builder.PRINCIPLE_TO_LABEL[dim]
                        source = "section_b"
                    elif fact.concept in builder.SECTION_C_CONCEPT_TO_LABEL:
                        label = builder.SECTION_C_CONCEPT_TO_LABEL[fact.concept]
                        source = "section_c"
                    elif fact.concept in builder.NOTES_PRINCIPLE_CONCEPTS:
                        label = builder.NOTES_PRINCIPLE_CONCEPTS[fact.concept]
                        source = "notes_principle"
                    else:
                        continue

                    counts[f"clean_labeled_candidates_{source}"] += 1
                    key = (company.id, fact.concept, clean_text)
                    labels = clean_labeled[key]
                    if label not in labels:
                        labels[label] = source
                    else:
                        counts[f"duplicate_same_label_candidates_{source}"] += 1

    final_by_source = Counter()
    conflict_entries_by_source = Counter()
    contradiction_groups = 0
    contradiction_label_entries = 0
    for labels in clean_labeled.values():
        if len(labels) > 1:
            contradiction_groups += 1
            contradiction_label_entries += len(labels)
            conflict_entries_by_source.update(labels.values())
            continue
        _, source = next(iter(labels.items()))
        final_by_source[source] += 1

    counts["unique_clean_labeled_dedup_groups_before_conflict_drop"] = len(clean_labeled)
    counts["contradictory_dedup_groups_dropped"] = contradiction_groups
    counts["contradictory_label_entries_in_dropped_groups"] = contradiction_label_entries
    for source in SOURCE_ORDER:
        counts[f"final_rows_{source}"] = final_by_source[source]
        counts[f"contradictory_label_entries_dropped_{source}"] = conflict_entries_by_source[source]

    counts["historical_section_b_user_reported"] = HISTORICAL_SECTION_B_REFERENCE
    counts["historical_reference_delta_vs_current_final"] = (
        HISTORICAL_SECTION_B_REFERENCE - final_by_source["section_b"]
    )
    counts["historical_reference_exactly_matches_current_raw_axis_facts"] = (
        HISTORICAL_SECTION_B_REFERENCE == counts["raw_valid_principle_axis_facts_all_concepts"]
    )
    return dict(counts)


def load_company_disjoint_test() -> pd.DataFrame:
    splits = {}
    for split in ("train", "val", "test"):
        path = SPLIT_DIR / f"{split}.csv"
        df = pd.read_csv(path, dtype={"cin": "string"})
        required = {"text", "label", "cin", "principle_id", "source"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"{path} missing required columns: {sorted(missing)}")
        df["cin_norm"] = df["cin"].fillna("").astype(str).str.strip().str.upper()
        splits[split] = df
    for a, b in (("train", "val"), ("train", "test"), ("val", "test")):
        overlap = set(splits[a]["cin_norm"]) & set(splits[b]["cin_norm"])
        if overlap:
            raise RuntimeError(f"Company overlap in split {a}/{b}: {len(overlap)} CINs")

    test = splits["test"].copy()
    if test["cin_norm"].eq("").any():
        raise ValueError("Company-disjoint test contains blank CIN values")
    test["label"] = pd.to_numeric(test["label"], errors="raise").astype(int)
    if not test["label"].isin(range(9)).all():
        raise ValueError("Expected labels 0..8")
    expected = test["principle_id"].str.extract(r"Principle([1-9])Member")[0].astype(int) - 1
    if not np.array_equal(expected.to_numpy(), test["label"].to_numpy()):
        raise ValueError("label/principle_id mismatch in test split")
    if not set(test["source"].dropna().unique()).issubset(SOURCE_ORDER):
        raise ValueError(f"Unexpected source values: {sorted(set(test['source'].dropna().unique()))}")
    return test


def predict(texts: list[str]) -> np.ndarray:
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Stage 3 seed-99 model not found: {MODEL_PATH}")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tokenizer = AutoTokenizer.from_pretrained(str(MODEL_PATH), local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(
        str(MODEL_PATH), local_files_only=True
    ).to(device)
    model.eval()
    if int(model.config.num_labels) != 9:
        raise ValueError(f"Expected 9 classifier outputs, found {model.config.num_labels}")
    outputs = []
    with torch.no_grad():
        for start in range(0, len(texts), INFERENCE_BATCH_SIZE):
            encoded = tokenizer(
                texts[start:start + INFERENCE_BATCH_SIZE], padding=True,
                truncation=True, max_length=512, return_tensors="pt",
            ).to(device)
            outputs.append(model(**encoded).logits.argmax(dim=-1).cpu().numpy())
    del model
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    return np.concatenate(outputs).astype(int)


def cluster_bootstrap_ci(hit: np.ndarray, groups: np.ndarray) -> list[float] | None:
    unique_groups = np.unique(groups)
    if len(unique_groups) < 2:
        return None
    rows_by_group = {g: np.flatnonzero(groups == g) for g in unique_groups}
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    samples = np.empty(BOOTSTRAP_REPS, dtype=float)
    for i in range(BOOTSTRAP_REPS):
        chosen = rng.choice(unique_groups, size=len(unique_groups), replace=True)
        idx = np.concatenate([rows_by_group[g] for g in chosen])
        samples[i] = hit[idx].mean()
    return [float(np.percentile(samples, 2.5)), float(np.percentile(samples, 97.5))]


def main() -> None:
    filter_diagnostics = collect_filter_diagnostics()
    test = load_company_disjoint_test()
    y = test["label"].to_numpy()
    preds = predict(test["text"].fillna("").astype(str).tolist())
    hit = preds == y

    source_metrics = {}
    for source in SOURCE_ORDER:
        mask = test["source"].eq(source).to_numpy()
        part = test.loc[mask]
        part_hit = hit[mask]
        source_metrics[source] = {
            "n": int(mask.sum()),
            "unique_cins": int(part["cin_norm"].nunique()),
            "correct": int(part_hit.sum()),
            "top1_accuracy": float(part_hit.mean()) if mask.any() else None,
            "macro_f1": float(f1_score(y[mask], preds[mask], labels=list(range(9)), average="macro", zero_division=0)) if mask.any() else None,
            "cin_cluster_bootstrap_ci95": cluster_bootstrap_ci(part_hit, part["cin_norm"].to_numpy()) if mask.any() else None,
            "per_principle": {},
        }
        for label in range(9):
            class_mask = mask & (y == label)
            source_metrics[source]["per_principle"][f"P{label + 1}"] = {
                "n": int(class_mask.sum()),
                "correct": int(hit[class_mask].sum()),
                "accuracy": float(hit[class_mask].mean()) if class_mask.any() else None,
            }

    report = {
        "purpose": "Stage 2 filter-count reconciliation and Stage 3 company-disjoint source-wise accuracy",
        "data_root": "data/brsr.db (via configured BRSR_DB_URL)",
        "filter_count_diagnostics": filter_diagnostics,
        "model": str(MODEL_PATH.relative_to(BASE)),
        "test_split": str((SPLIT_DIR / "test.csv").relative_to(BASE)),
        "test_n": int(len(test)),
        "test_unique_cins": int(test["cin_norm"].nunique()),
        "company_disjoint_assertions": True,
        "overall_top1_accuracy": float(hit.mean()),
        "overall_correct": int(hit.sum()),
        "source_metrics": source_metrics,
        "interpretation_limits": [
            "Section B source labels come from PrincipleAxis; Section C labels come from concept-name mapping; Notes labels come from NotesPrinciple concept names.",
            "Source-wise accuracy is measured against those source-derived labels, not independent human ground truth.",
            "High Section B accuracy is informative but does not by itself eliminate template or taxonomy leakage concerns.",
            "The user-reported historical 17,219 count has no generating query or dated source artifact in the current repository; compare it to the current DB filter funnel before asserting a definitive cause.",
            "AI-assisted Section C mappings are weak labels and are not expert-verified.",
        ],
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("STAGE 2 — FILTER FUNNEL AND SOURCE-WISE HELD-OUT AUDIT")
    print("Current database Section B count funnel:")
    for key in (
        "raw_valid_principle_axis_facts_all_concepts",
        "section_b_explanatory_facts",
        "section_b_clean_candidates",
        "clean_labeled_candidates_section_b",
        "duplicate_same_label_candidates_section_b",
        "section_b_noise_filtered",
        "final_rows_section_b",
        "contradictory_dedup_groups_dropped",
    ):
        print(f"  {key}: {filter_diagnostics.get(key, 0)}")
    print(f"Historical 17,219 matches current raw valid PrincipleAxis facts: {filter_diagnostics['historical_reference_exactly_matches_current_raw_axis_facts']}")
    print(f"Company-disjoint test: N={len(test)}, CINs={test['cin_norm'].nunique()}, overall top1={hit.mean():.4f}")
    for source, metrics in source_metrics.items():
        print(
            f"{source}: N={metrics['n']}, CINs={metrics['unique_cins']}, "
            f"Top1={metrics['top1_accuracy']:.4f}, "
            f"CI95(CIN bootstrap)={metrics['cin_cluster_bootstrap_ci95']}"
        )
    print(f"JSON report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
