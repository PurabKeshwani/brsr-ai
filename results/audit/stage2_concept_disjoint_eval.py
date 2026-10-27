"""Concept-disjoint diagnostic for Section C principle classification.

Reconstructs concept names from the read-only BRSR database, removes a
deterministic 20% of Section C concepts from every training/validation source,
re-trains one classifier seed from the domain-adapted encoder, and evaluates
only held-out Section C concepts on the existing company-disjoint test firms.

Run from repository root with .venv-ml. This performs model training and test
inference when the user runs it; the assistant does not run it.
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.metrics import classification_report, f1_score
from torch.utils.data import Dataset
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    DataCollatorWithPadding,
    Trainer,
    TrainingArguments,
)

BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE / "src"))
sys.path.insert(0, str(BASE / "scripts" / "03_bert_training"))

import build_training_dataset as builder  # noqa: E402
from db.models import Company, Fact, Filing  # noqa: E402
from db.session import get_session  # noqa: E402

SPLIT_DIR = BASE / "data" / "training_company_split"
ARTIFACT_DIR = BASE / "data" / "training_concept_disjoint"
MODEL_SOURCE = BASE / "data" / "models" / "domain_adapted_bert" / "final_model"
BASELINE_MODEL = BASE / "data" / "models" / "brsr_company_split_classifier" / "seed_99" / "best_model"
OUTPUT_MODEL = BASE / "data" / "models" / "brsr_concept_disjoint_classifier" / "seed_42"
REPORT_PATH = BASE / "results" / "audit" / "stage2_concept_disjoint_results.json"

SEED = 42
HELDOUT_CONCEPT_FRACTION = 0.20
NUM_LABELS = 9
MAX_LENGTH = 512
BATCH_SIZE = 4
GRAD_ACCUM = 4
NUM_EPOCHS = 5
LEARNING_RATE = 2e-5
BOOTSTRAP_REPS = 2000
BOOTSTRAP_SEED = 420


def normalize_text(text: object) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def reconstruct_final_sample_concepts() -> dict[tuple[str, str, str, int], set[str]]:
    """Mirror builder selection/dedup and map final CSV row keys to concepts."""
    company_by_id: dict[int, Company] = {}
    # (company_id, concept, cleaned text) -> label -> source
    labeled: dict[tuple[int, str, str], dict[int, str]] = defaultdict(dict)
    with get_session() as session:
        companies = session.query(Company).all()
        company_by_id = {company.id: company for company in companies}
        for company in companies:
            filings = session.query(Filing).filter_by(company_id=company.id).all()
            for filing in filings:
                facts = (
                    session.query(Fact)
                    .filter(Fact.filing_id == filing.id,
                            Fact.concept.like("%ExplanatoryTextBlock%"))
                    .all()
                )
                for fact in facts:
                    if not fact.value:
                        continue
                    raw = fact.value.strip()
                    if not builder.is_clean_narrative(raw):
                        continue
                    text = builder.URL_PATTERN.sub("", raw).strip()
                    text = re.sub(r"\s+", " ", text).strip()

                    axis = (fact.dimensions or {}).get("PrincipleAxis")
                    if axis in builder.PRINCIPLE_TO_LABEL:
                        label, source = builder.PRINCIPLE_TO_LABEL[axis], "section_b"
                    elif fact.concept in builder.SECTION_C_CONCEPT_TO_LABEL:
                        label, source = builder.SECTION_C_CONCEPT_TO_LABEL[fact.concept], "section_c"
                    elif fact.concept in builder.NOTES_PRINCIPLE_CONCEPTS:
                        label, source = builder.NOTES_PRINCIPLE_CONCEPTS[fact.concept], "notes_principle"
                    else:
                        continue

                    key = (company.id, fact.concept, text)
                    labeled[key][label] = source

    # Map only groups which survive the builder's contradictory-label rule.
    mapping: dict[tuple[str, str, str, int], set[str]] = defaultdict(set)
    for (company_id, concept, text), labels in labeled.items():
        if len(labels) != 1:
            continue
        label, source = next(iter(labels.items()))
        company = company_by_id[company_id]
        cin = str(company.cin or "").strip().upper()
        mapping[(cin, source, text, int(label))].add(concept)
    return mapping


def load_and_annotate_splits(concept_map: dict) -> tuple[dict[str, pd.DataFrame], dict]:
    frames = {}
    counts = {}
    for split in ("train", "val", "test"):
        df = pd.read_csv(SPLIT_DIR / f"{split}.csv", dtype={"cin": "string"})
        needed = {"text", "label", "cin", "principle_id", "source"}
        missing = needed - set(df.columns)
        if missing:
            raise ValueError(f"{split}.csv missing columns: {sorted(missing)}")
        df["cin_norm"] = df["cin"].fillna("").astype(str).str.strip().str.upper()
        df["text_norm"] = df["text"].fillna("").map(normalize_text)
        df["label"] = pd.to_numeric(df["label"], errors="raise").astype(int)
        keys = list(zip(df["cin_norm"], df["source"], df["text_norm"], df["label"]))
        concept_sets = [concept_map.get(key, set()) for key in keys]
        df["concept"] = [next(iter(value)) if len(value) == 1 else None for value in concept_sets]
        df["concept_match_status"] = [
            "unique" if len(value) == 1 else "ambiguous" if len(value) > 1 else "unmatched"
            for value in concept_sets
        ]
        counts[split] = {
            "rows": int(len(df)),
            "unique_concept_match": int((df["concept_match_status"] == "unique").sum()),
            "ambiguous_concept_match": int((df["concept_match_status"] == "ambiguous").sum()),
            "unmatched_concept": int((df["concept_match_status"] == "unmatched").sum()),
        }
        # Fail closed: an unmatched Section C row could conceal a held-out concept.
        bad_c = df[(df.source == "section_c") & (df.concept_match_status == "unmatched")]
        if len(bad_c):
            raise RuntimeError(
                f"Cannot prove concept disjointness: {len(bad_c)} {split} Section C rows do not map to a DB concept."
            )
        frames[split] = df

    cins = {name: set(df["cin_norm"]) for name, df in frames.items()}
    if any(df["cin_norm"].eq("").any() for df in frames.values()):
        raise ValueError("A company-disjoint split contains blank CIN values")
    for a, b in (("train", "val"), ("train", "test"), ("val", "test")):
        if cins[a] & cins[b]:
            raise RuntimeError(f"Company split overlap {a}/{b}: {len(cins[a] & cins[b])} CINs")
    return frames, counts


class BRSRDataset(Dataset):
    def __init__(self, texts: list[str], labels: list[int], tokenizer):
        self.texts, self.labels, self.tokenizer = texts, labels, tokenizer

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        row = self.tokenizer(self.texts[idx], truncation=True, max_length=MAX_LENGTH)
        row["labels"] = int(self.labels[idx])
        return row


class WeightedTrainer(Trainer):
    def __init__(self, class_weights=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.class_weights = class_weights

    def compute_loss(self, model, inputs, return_outputs=False, num_items_in_batch=None):
        labels = inputs["labels"]
        outputs = model(**inputs)
        loss = nn.CrossEntropyLoss(weight=self.class_weights.to(outputs.logits.device))(
            outputs.logits.view(-1, NUM_LABELS), labels.view(-1)
        )
        return (loss, outputs) if return_outputs else loss


def metric_fn(eval_pred):
    logits, labels = eval_pred
    pred = np.argmax(logits, axis=-1)
    top2 = np.argsort(logits, axis=-1)[:, -2:]
    return {
        "accuracy": float(np.mean(pred == labels)),
        "top2_accuracy": float(np.mean(np.any(top2 == labels[:, None], axis=-1))),
        "macro_f1": float(f1_score(labels, pred, labels=list(range(NUM_LABELS)), average="macro", zero_division=0)),
    }


def bootstrap_ci(hit: np.ndarray, groups: np.ndarray) -> list[float] | None:
    names = np.unique(groups)
    if len(names) < 2:
        return None
    rows = {name: np.flatnonzero(groups == name) for name in names}
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    values = []
    for _ in range(BOOTSTRAP_REPS):
        sampled = rng.choice(names, size=len(names), replace=True)
        idx = np.concatenate([rows[name] for name in sampled])
        values.append(float(hit[idx].mean()))
    return [float(np.percentile(values, 2.5)), float(np.percentile(values, 97.5))]


def infer(model_dir: Path, df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    tokenizer = AutoTokenizer.from_pretrained(str(model_dir), local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(str(model_dir), local_files_only=True)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device).eval()
    if int(model.config.num_labels) != NUM_LABELS:
        raise ValueError(f"Expected {NUM_LABELS} output labels at {model_dir}")
    logits_all = []
    with torch.no_grad():
        texts = df["text"].fillna("").astype(str).tolist()
        for start in range(0, len(texts), 8):
            encoded = tokenizer(texts[start:start + 8], padding=True, truncation=True,
                                max_length=MAX_LENGTH, return_tensors="pt").to(device)
            logits_all.append(model(**encoded).logits.float().cpu().numpy())
    del model
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    logits = np.vstack(logits_all)
    return np.argmax(logits, axis=1), np.argsort(logits, axis=1)[:, -2:]


def summarize(df: pd.DataFrame, pred: np.ndarray, top2: np.ndarray) -> dict:
    y = df["label"].to_numpy()
    hit1 = pred == y
    hit2 = np.any(top2 == y[:, None], axis=1)
    return {
        "n": int(len(df)),
        "unique_cins": int(df["cin_norm"].nunique()),
        "unique_concepts": int(df["concept"].nunique()),
        "top1_correct": int(hit1.sum()),
        "top1_accuracy": float(hit1.mean()),
        "top1_cin_cluster_bootstrap_ci95": bootstrap_ci(hit1, df["cin_norm"].to_numpy()),
        "top2_correct": int(hit2.sum()),
        "top2_accuracy": float(hit2.mean()),
        "macro_f1": float(f1_score(y, pred, labels=list(range(NUM_LABELS)), average="macro", zero_division=0)),
        "per_principle": {
            f"P{i + 1}": {
                "n": int((y == i).sum()),
                "top1_accuracy": float(hit1[y == i].mean()) if np.any(y == i) else None,
                "top2_accuracy": float(hit2[y == i].mean()) if np.any(y == i) else None,
            }
            for i in range(NUM_LABELS)
        },
    }


def main() -> None:
    if not MODEL_SOURCE.exists():
        raise FileNotFoundError(f"Local domain-adapted base model missing: {MODEL_SOURCE}")
    if not BASELINE_MODEL.exists():
        raise FileNotFoundError(f"Company-disjoint baseline missing: {BASELINE_MODEL}")

    print("Reconstructing sample-to-concept links from local DB (read-only)...")
    concept_map = reconstruct_final_sample_concepts()
    frames, match_counts = load_and_annotate_splits(concept_map)
    test_c = frames["test"][(frames["test"].source == "section_c") & (frames["test"].concept_match_status == "unique")].copy()
    concepts = sorted(test_c["concept"].unique())
    if len(concepts) < 5:
        raise RuntimeError(f"Only {len(concepts)} uniquely identified Section C test concepts; insufficient for 20% holdout.")
    rng = np.random.default_rng(SEED)
    heldout = []
    concept_labels = test_c.groupby("concept")["label"].agg(lambda values: int(values.mode().iloc[0]))
    # Stratify the concept holdout by the weak label. For principles represented
    # by only one test concept, retain that concept for training support and
    # document its absence from the held-out-concept estimate.
    for label in sorted(concept_labels.unique()):
        label_concepts = sorted(concept_labels[concept_labels == label].index.tolist())
        if len(label_concepts) < 2:
            continue
        n_hold = min(len(label_concepts) - 1, max(1, int(round(len(label_concepts) * HELDOUT_CONCEPT_FRACTION))))
        heldout.extend(rng.choice(label_concepts, size=n_hold, replace=False).tolist())
    heldout = sorted(heldout)
    if not heldout:
        raise RuntimeError("No held-out concepts selected; each represented class had fewer than two concepts.")
    heldout_n = len(heldout)
    heldout_set = set(heldout)

    # Remove every row with an ambiguous concept from all splits. For uniquely
    # mapped rows, purge held-out concepts from train and validation regardless
    # of source, then evaluate only Section C rows for those concepts.
    filtered = {}
    for split, df in frames.items():
        unique = df[df["concept_match_status"] == "unique"].copy()
        if split in ("train", "val"):
            unique = unique[~unique["concept"].isin(heldout_set)].copy()
        filtered[split] = unique
    train_df, val_df = filtered["train"], filtered["val"]
    eval_df = filtered["test"][(filtered["test"].source == "section_c") & filtered["test"].concept.isin(heldout_set)].copy()
    if train_df.empty or val_df.empty or eval_df.empty:
        raise RuntimeError("Concept-disjoint train/validation/evaluation split is empty; aborting.")
    train_concepts = set(train_df["concept"])
    val_concepts = set(val_df["concept"])
    if train_concepts & heldout_set or val_concepts & heldout_set:
        raise RuntimeError("Held-out concepts remain in training or validation rows")
    if set(eval_df["source"]) != {"section_c"}:
        raise RuntimeError("Evaluation must contain only Section C rows")

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    train_df.to_csv(ARTIFACT_DIR / "train.csv", index=False)
    val_df.to_csv(ARTIFACT_DIR / "val.csv", index=False)
    eval_df.to_csv(ARTIFACT_DIR / "test_section_c_heldout_concepts.csv", index=False)
    (ARTIFACT_DIR / "heldout_concepts.json").write_text(json.dumps(heldout, indent=2), encoding="utf-8")

    print(f"Concept matching coverage: {json.dumps(match_counts)}")
    print(f"Held-out concepts: {len(heldout)} / {len(concepts)}; test rows={len(eval_df)}")
    print("Purged held-out concepts from train and validation; company-disjoint test companies preserved.")

    # Baseline is evaluated on exactly the same held-out concept test rows.
    baseline_pred, baseline_top2 = infer(BASELINE_MODEL, eval_df)
    baseline_metrics = summarize(eval_df, baseline_pred, baseline_top2)

    torch.manual_seed(SEED)
    np.random.seed(SEED)
    tokenizer = AutoTokenizer.from_pretrained(str(MODEL_SOURCE), local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(
        str(MODEL_SOURCE), num_labels=NUM_LABELS,
        problem_type="single_label_classification", local_files_only=True,
    )
    labels = train_df["label"].to_numpy()
    counts = np.bincount(labels, minlength=NUM_LABELS)
    raw_weights = np.ones(NUM_LABELS, dtype=np.float32)
    present = counts > 0
    raw_weights[present] = len(labels) / (present.sum() * counts[present])
    smooth_weights = np.sqrt(raw_weights)
    smooth_weights /= smooth_weights.mean()
    class_weights = torch.tensor(smooth_weights, dtype=torch.float)

    train_ds = BRSRDataset(train_df["text"].fillna("").astype(str).tolist(), labels.tolist(), tokenizer)
    val_ds = BRSRDataset(val_df["text"].fillna("").astype(str).tolist(), val_df["label"].astype(int).tolist(), tokenizer)
    collator = DataCollatorWithPadding(tokenizer=tokenizer)
    import inspect
    kwargs = inspect.signature(TrainingArguments.__init__).parameters
    eval_arg = "eval_strategy" if "eval_strategy" in kwargs else "evaluation_strategy"
    args = TrainingArguments(
        output_dir=str(OUTPUT_MODEL / "checkpoints"),
        num_train_epochs=NUM_EPOCHS,
        per_device_train_batch_size=BATCH_SIZE,
        per_device_eval_batch_size=BATCH_SIZE * 2,
        gradient_accumulation_steps=GRAD_ACCUM,
        learning_rate=LEARNING_RATE,
        weight_decay=0.01,
        warmup_steps=300,
        lr_scheduler_type="cosine",
        load_best_model_at_end=True,
        metric_for_best_model="macro_f1",
        greater_is_better=True,
        save_total_limit=2,
        logging_steps=100,
        fp16=torch.cuda.is_available(),
        report_to="none",
        seed=SEED,
        **{eval_arg: "epoch", "save_strategy": "epoch"},
    )
    trainer = WeightedTrainer(
        class_weights=class_weights,
        model=model,
        args=args,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        data_collator=collator,
        compute_metrics=metric_fn,
    )
    trainer.train()
    OUTPUT_MODEL.mkdir(parents=True, exist_ok=True)
    trainer.save_model(str(OUTPUT_MODEL / "best_model"))
    tokenizer.save_pretrained(str(OUTPUT_MODEL / "best_model"))
    new_pred, new_top2 = infer(OUTPUT_MODEL / "best_model", eval_df)
    new_metrics = summarize(eval_df, new_pred, new_top2)

    delta_hit = (new_pred == eval_df["label"].to_numpy()).astype(float) - (baseline_pred == eval_df["label"].to_numpy()).astype(float)
    delta_ci = bootstrap_ci(delta_hit + 1.0, eval_df["cin_norm"].to_numpy())
    if delta_ci is not None:
        delta_ci = [delta_ci[0] - 1.0, delta_ci[1] - 1.0]
    result = {
        "evaluation": "Section C concept-disjoint diagnostic on company-disjoint test companies",
        "selection": {"seed": SEED, "fraction": HELDOUT_CONCEPT_FRACTION, "heldout_concepts": heldout},
        "concept_match_counts": match_counts,
        "source_company_disjoint": True,
        "train_rows_after_purge": int(len(train_df)),
        "val_rows_after_purge": int(len(val_df)),
        "eval_source": "section_c",
        "evaluation_rows": int(len(eval_df)),
        "evaluation_unique_cins": int(eval_df["cin_norm"].nunique()),
        "heldout_concepts_absent_from_train_and_val": not (train_concepts & heldout_set or val_concepts & heldout_set),
        "baseline_full_concept_model": {"path": str(BASELINE_MODEL.relative_to(BASE)), **baseline_metrics},
        "concept_disjoint_model": {"path": str((OUTPUT_MODEL / "best_model").relative_to(BASE)), **new_metrics},
        "paired_top1_delta_new_minus_baseline": {
            "estimate": float(delta_hit.mean()),
            "cin_cluster_bootstrap_ci95": delta_ci,
        },
        "training": {
            "base_encoder": str(MODEL_SOURCE.relative_to(BASE)),
            "seed": SEED,
            "epochs": NUM_EPOCHS,
            "learning_rate": LEARNING_RATE,
            "max_length": MAX_LENGTH,
            "selection_metric": "validation macro-F1 only",
            "test_used_for_tuning": False,
        },
        "limitations": [
            "Labels remain taxonomy-derived weak labels; this measures agreement with those labels, not human-ground-truth semantic understanding.",
            "Concepts are reconstructed from the local DB using exact company/source/label/cleaned-text matching; ambiguous rows are excluded, and unmatched Section C rows cause a fail-closed error.",
            "This is one-seed diagnostic evidence; concepts are sampled once with fixed seed 42 and the result must be reported as a diagnostic, not used to tune and re-evaluate the same test set.",
            "Domain-adaptive pretraining may have exposed the model to corpus wording, although this supervised split withholds the selected concept IDs.",
        ],
    }
    REPORT_PATH.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("\nCONCEPT-DISJOINT SECTION C EVALUATION")
    print(f"Baseline full-concept model: Top1={baseline_metrics['top1_accuracy']:.4f}, Top2={baseline_metrics['top2_accuracy']:.4f}")
    print(f"Concept-disjoint model: Top1={new_metrics['top1_accuracy']:.4f}, Top2={new_metrics['top2_accuracy']:.4f}")
    print(f"Paired delta (new-baseline): {delta_hit.mean():+.4f} CI95={delta_ci}")
    print(f"Held-out concepts={len(heldout)}; N={len(eval_df)}; CINs={eval_df['cin_norm'].nunique()}")
    print(f"Results: {REPORT_PATH}")


if __name__ == "__main__":
    main()
