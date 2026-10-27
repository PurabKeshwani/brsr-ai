"""Stage 5 supervised-transfer evaluation on Stage 3's company-disjoint test set.

Compares the Stage 3 seed-99 supervised classifier with the existing zero-shot
MPNet principle-definition + anchor hybrid on the identical held-out segments.
Reports CIN-cluster bootstrap CIs and paired bootstrap deltas. This script does
not train or tune either method. Run with the repository's .venv-ml Python.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import classification_report, confusion_matrix, f1_score
from transformers import AutoModelForSequenceClassification, AutoTokenizer

BASE = Path(__file__).resolve().parents[2]
SRC = BASE / "src"
sys.path.insert(0, str(SRC))

SPLIT_DIR = BASE / "data/training_company_split"
TEST_PATH = SPLIT_DIR / "test.csv"
TRAIN_PATH = SPLIT_DIR / "train.csv"
VAL_PATH = SPLIT_DIR / "val.csv"
SUPERVISED_MODEL_PATH = BASE / "data/models/brsr_company_split_classifier/seed_99/best_model"
RESULT_PATH = BASE / "results/audit/stage5_company_disjoint_results.json"
BOOTSTRAP_REPS = 2000
BOOTSTRAP_SEED = 42
INFERENCE_BATCH_SIZE = 8
LABEL_TO_PRINCIPLE = {i: i + 1 for i in range(9)}


def assert_company_disjoint() -> tuple[pd.DataFrame, set[str]]:
    frames = {}
    for name, path in (("train", TRAIN_PATH), ("val", VAL_PATH), ("test", TEST_PATH)):
        df = pd.read_csv(path, dtype={"cin": "string"})
        required = {"text", "label", "cin", "principle_id"}
        if not required.issubset(df.columns):
            raise ValueError(f"{path} missing required columns: {sorted(required - set(df.columns))}")
        df["cin_norm"] = df["cin"].fillna("").astype(str).str.strip().str.upper()
        frames[name] = df
    cins = {name: set(df["cin_norm"]) for name, df in frames.items()}
    for left, right in (("train", "val"), ("train", "test"), ("val", "test")):
        overlap = cins[left] & cins[right]
        if overlap:
            raise RuntimeError(f"Stage 3 company split is not disjoint: {left}/{right} overlap={len(overlap)}")
    test = frames["test"].copy()
    if test["cin_norm"].eq("").any():
        raise ValueError("Test split contains empty CIN values; cluster bootstrap cannot proceed safely.")
    test["label"] = pd.to_numeric(test["label"], errors="raise").astype(int)
    if not test["label"].isin(range(9)).all():
        raise ValueError("Expected zero-based Stage 3 labels 0 through 8.")
    if not test["principle_id"].astype(str).str.fullmatch(r"Principle[1-9]Member").all():
        raise ValueError("Unexpected principle_id values in test split.")
    expected_labels = test["principle_id"].str.extract(r"Principle([1-9])Member")[0].astype(int) - 1
    if not np.array_equal(test["label"].to_numpy(), expected_labels.to_numpy()):
        raise ValueError("Numeric labels do not match principle_id values; refusing to score misaligned classes.")
    return test, cins["test"]


def supervised_topk_predictions(texts: list[str]) -> tuple[np.ndarray, np.ndarray]:
    if not SUPERVISED_MODEL_PATH.exists():
        raise FileNotFoundError(f"Stage 3 seed-99 classifier not found: {SUPERVISED_MODEL_PATH}")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tokenizer = AutoTokenizer.from_pretrained(str(SUPERVISED_MODEL_PATH))
    model = AutoModelForSequenceClassification.from_pretrained(str(SUPERVISED_MODEL_PATH)).to(device)
    model.eval()
    if int(model.config.num_labels) != 9:
        raise ValueError(f"Expected 9 classifier outputs, found {model.config.num_labels}")
    pred_batches = []
    top2_batches = []
    with torch.no_grad():
        for start in range(0, len(texts), INFERENCE_BATCH_SIZE):
            batch = texts[start:start + INFERENCE_BATCH_SIZE]
            encoded = tokenizer(
                batch, padding=True, truncation=True, max_length=512, return_tensors="pt"
            ).to(device)
            logits = model(**encoded).logits
            pred_batches.append(logits.argmax(dim=-1).cpu().numpy())
            top2_batches.append(torch.topk(logits, k=2, dim=-1).indices.cpu().numpy())
    del model
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    return np.concatenate(pred_batches).astype(int), np.vstack(top2_batches).astype(int)


def topk_predictions(texts: list[str]) -> tuple[np.ndarray, np.ndarray]:
    """Compute zero-shot hybrid top-1 and top-2 IDs for all nine principles."""
    from analysis.compliance.compliance_mapper import (
        _get_model,
        _get_principle_embeddings,
        _get_principle_anchor_embeddings,
    )
    from sentence_transformers import util

    model = _get_model()
    principle_nums, principle_embeddings = _get_principle_embeddings()
    anchor_dict = _get_principle_anchor_embeddings()
    emb = model.encode(texts, batch_size=INFERENCE_BATCH_SIZE, convert_to_tensor=True, show_progress_bar=True)
    score_columns = []
    for idx, principle in enumerate(principle_nums):
        enriched = util.cos_sim(emb, principle_embeddings[idx:idx + 1]).squeeze(1)
        anchor = util.cos_sim(emb, anchor_dict[principle])
        score_columns.append(0.5 * enriched + 0.5 * (0.70 * anchor.max(dim=1).values + 0.30 * anchor.mean(dim=1)))
    matrix = torch.stack(score_columns, dim=1)
    top2 = torch.topk(matrix, k=2, dim=1).indices.cpu().numpy().astype(int)
    top1 = top2[:, 0].copy()
    del model, principle_embeddings, anchor_dict, emb, matrix, score_columns
    _get_model.cache_clear()
    _get_principle_embeddings.cache_clear()
    _get_principle_anchor_embeddings.cache_clear()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    return top1, top2


def main() -> None:
    test, test_cins = assert_company_disjoint()
    texts = test["text"].fillna("").astype(str).tolist()
    y = test["label"].to_numpy()
    groups = test["cin_norm"].to_numpy()

    print(f"Company-disjoint test set verified: N={len(test)}, CINs={len(test_cins)}")
    print("Computing zero-shot MPNet definition + anchor hybrid (same held-out rows)...")
    zero_top1, zero_top2 = topk_predictions(texts)
    print("Computing Stage 3 seed-99 supervised classifier (same held-out rows)...")
    sup_top1, sup_top2 = supervised_topk_predictions(texts)

    zero_top1_hit = zero_top1 == y
    zero_top2_hit = np.any(zero_top2 == y[:, None], axis=1)
    sup_top1_hit = sup_top1 == y
    sup_top2_hit = np.any(sup_top2 == y[:, None], axis=1)

    # CIN-cluster bootstrap: resample companies with replacement and retain
    # every test segment belonging to each selected company.
    unique_groups = np.unique(groups)
    rows_by_group = {g: np.flatnonzero(groups == g) for g in unique_groups}
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    boot = {k: [] for k in ("zero_top1", "zero_top2", "sup_top1", "sup_top2", "delta_top1", "delta_top2")}
    for _ in range(BOOTSTRAP_REPS):
        sampled = rng.choice(unique_groups, size=len(unique_groups), replace=True)
        idx = np.concatenate([rows_by_group[g] for g in sampled])
        z1 = float(zero_top1_hit[idx].mean())
        z2 = float(zero_top2_hit[idx].mean())
        s1 = float(sup_top1_hit[idx].mean())
        s2 = float(sup_top2_hit[idx].mean())
        boot["zero_top1"].append(z1)
        boot["zero_top2"].append(z2)
        boot["sup_top1"].append(s1)
        boot["sup_top2"].append(s2)
        boot["delta_top1"].append(s1 - z1)
        boot["delta_top2"].append(s2 - z2)
    ci = {k: [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))] for k, v in boot.items()}

    per_principle = {}
    for label in range(9):
        mask = y == label
        name = f"Principle{label + 1}"
        per_principle[name] = {
            "support": int(mask.sum()),
            "zero_shot_top1_correct": int(zero_top1_hit[mask].sum()),
            "zero_shot_top1_accuracy": float(zero_top1_hit[mask].mean()) if mask.any() else None,
            "supervised_top1_correct": int(sup_top1_hit[mask].sum()),
            "supervised_top1_accuracy": float(sup_top1_hit[mask].mean()) if mask.any() else None,
        }

    result = {
        "evaluation": "Stage 5 supervised transfer vs zero-shot MPNet anchor hybrid",
        "test_dataset": str(TEST_PATH.relative_to(BASE)),
        "n_segments": int(len(test)),
        "n_company_clusters_cin": int(len(test_cins)),
        "stage3_company_disjoint_assertions": True,
        "supervised_model": str(SUPERVISED_MODEL_PATH.relative_to(BASE)),
        "supervised_model_selection": "seed 99, selected on Stage 3 validation macro-F1; Stage 3 checkpoint LayerNorm restore warning remains under review",
        "zero_shot_method": "all-mpnet-base-v2 against official principle definitions and anchors; 0.5 definition + 0.5 anchor score; anchor=0.70 max + 0.30 mean, matching existing mapper hybrid logic",
        "comparison_framing": "supervised transfer vs zero-shot embedding on identical Stage 3 company-disjoint test segments; not an isolated alignment-scoring improvement",
        "bootstrap": {"method": "CIN cluster bootstrap, paired between methods", "replicates": BOOTSTRAP_REPS, "seed": BOOTSTRAP_SEED, "ci_level": 0.95, "intervals": ci},
        "metrics": {
            "zero_shot": {
                "top1": float(zero_top1_hit.mean()),
                "top1_correct": int(zero_top1_hit.sum()),
                "top2": float(zero_top2_hit.mean()),
                "top2_correct": int(zero_top2_hit.sum()),
                "macro_f1_top1": float(f1_score(y, zero_top1, average="macro", zero_division=0)),
                "top1_ci95": ci["zero_top1"],
                "top2_ci95": ci["zero_top2"],
                "confusion_matrix": confusion_matrix(y, zero_top1, labels=list(range(9))).tolist(),
            },
            "supervised_transfer": {
                "top1": float(sup_top1_hit.mean()),
                "top1_correct": int(sup_top1_hit.sum()),
                "top2": float(sup_top2_hit.mean()),
                "top2_correct": int(sup_top2_hit.sum()),
                "macro_f1_top1": float(f1_score(y, sup_top1, average="macro", zero_division=0)),
                "top1_ci95": ci["sup_top1"],
                "top2_ci95": ci["sup_top2"],
                "confusion_matrix": confusion_matrix(y, sup_top1, labels=list(range(9))).tolist(),
                "classification_report": classification_report(y, sup_top1, labels=list(range(9)), output_dict=True, zero_division=0),
            },
            "paired_delta_supervised_minus_zero_shot": {
                "top1": float(sup_top1_hit.mean() - zero_top1_hit.mean()),
                "top1_ci95": ci["delta_top1"],
                "top2": float(sup_top2_hit.mean() - zero_top2_hit.mean()),
                "top2_ci95": ci["delta_top2"],
            },
        },
        "per_principle_top1": per_principle,
        "limitations": [
            "Stage 3 checkpoint-restoration LayerNorm warning must be resolved before treating the supervised checkpoint as final.",
            "Stage 3 labels are weak labels from the existing BRSR mapping pipeline, not independently expert-verified ground truth.",
            "This is supervised classifier transfer compared with zero-shot embedding, not a causal estimate of representation adaptation alone.",
            "Results evaluate Top-k principle classification on Stage 3 test segments; they do not directly establish regulatory compliance.",
        ],
    }
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("\nSTAGE 5 — COMPANY-DISJOINT TEST EVALUATION")
    print(f"N={len(test)} segments; {len(test_cins)} CINs; company-disjoint split assertions PASS")
    for key, title in (("zero_shot", "Zero-shot MPNet hybrid"), ("supervised_transfer", "Stage 3 supervised transfer")):
        m = result["metrics"][key]
        print(f"{title}: Top-1={m['top1']:.4f} CI95={m['top1_ci95']}; Top-2={m['top2']:.4f} CI95={m['top2_ci95']}")
    delta = result["metrics"]["paired_delta_supervised_minus_zero_shot"]
    print(f"Paired delta (supervised - zero-shot): Top-1={delta['top1']:.4f} CI95={delta['top1_ci95']}; Top-2={delta['top2']:.4f} CI95={delta['top2_ci95']}")
    print("Framing: supervised transfer vs zero-shot embedding; Stage 3 checkpoint warning remains.")
    print(f"Results: {RESULT_PATH}")


if __name__ == "__main__":
    main()
