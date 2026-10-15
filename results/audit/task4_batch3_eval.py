"""
TASK 4 — Stage 4 Greenwashing: Batch 3 Held-Out Evaluation
============================================================
Evaluates the FROZEN detector on Batch 3 (70 segments) AFTER human labeling.
This script must be run ONLY ONCE, after human_label is filled in
data/labeling_sheets/stage4_batch3_clean.csv.

BLOCKED: Requires human_label_rater_A and human_label_rater_B to be filled.

Run from repo root:
  python results/audit/task4_batch3_eval.py

Outputs:
  results/audit/task4_stage4_results.json
  results/audit/task4_stage4_log.txt
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import numpy as np
from sklearn.metrics import (
    f1_score, precision_recall_fscore_support,
    roc_auc_score, confusion_matrix, classification_report
)

BASE = Path("d:/brsr-ai-phase0-1/brsr-ai")
AUDIT_DIR = BASE / "results/audit"
AUDIT_DIR.mkdir(parents=True, exist_ok=True)

BATCH3_LABELS_PATH = BASE / "data/labeling_sheets/stage4_batch3_clean.csv"
BATCH3_ORIG_PATH = BASE / "data/validation/vagueness_validation_sample_batch3.csv"
BATCH12_PATH = BASE / "data/validation/vagueness_validation_sample.csv"
BATCH12B_PATH = BASE / "data/validation/vagueness_validation_sample_batch2.csv"

LOG_PATH = AUDIT_DIR / "task4_stage4_log.txt"
RESULTS_JSON = AUDIT_DIR / "task4_stage4_results.json"

lines: list[str] = []


def log(msg: str = "") -> None:
    print(msg)
    lines.append(msg)


def bootstrap_f1_ci(y_true, y_pred, n_boot=10000, seed=42):
    rng = np.random.default_rng(seed)
    n = len(y_true)
    fs = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, size=n)
        yt, yp = np.array(y_true)[idx], np.array(y_pred)[idx]
        if len(set(yt)) < 2:
            continue
        fs.append(f1_score(yt, yp, average="binary", zero_division=0))
    return float(np.percentile(fs, 2.5)), float(np.percentile(fs, 97.5))


def cohen_kappa(a, b):
    """Cohen's kappa between two raters."""
    n = len(a)
    p_o = np.mean(np.array(a) == np.array(b))
    p_a = (np.sum(np.array(a) == 1) / n) * (np.sum(np.array(b) == 1) / n) + \
           (np.sum(np.array(a) == 0) / n) * (np.sum(np.array(b) == 0) / n)
    return (p_o - p_a) / (1 - p_a + 1e-9)


def main():
    log("=" * 80)
    log("TASK 4 — STAGE 4 BATCH 3 HELD-OUT EVALUATION")
    log("=" * 80)
    log()

    # Check if labels are filled
    if not BATCH3_LABELS_PATH.exists():
        log(f"BLOCKED: {BATCH3_LABELS_PATH} does not exist.")
        log("Create it by running task0_label_provenance.py first, then fill human labels.")
        return

    labels_df = pd.read_csv(BATCH3_LABELS_PATH)
    rater_a_filled = labels_df["human_label_rater_A"].notna() & (labels_df["human_label_rater_A"].astype(str).str.strip() != "")
    rater_b_filled = labels_df["human_label_rater_B"].notna() & (labels_df["human_label_rater_B"].astype(str).str.strip() != "")

    log(f"Batch 3 clean sheet: {BATCH3_LABELS_PATH}")
    log(f"  Total rows: {len(labels_df)}")
    log(f"  Rater A filled: {rater_a_filled.sum()}")
    log(f"  Rater B filled: {rater_b_filled.sum()}")
    log()

    if rater_a_filled.sum() < len(labels_df) or rater_b_filled.sum() < len(labels_df):
        log("BLOCKED: Not all rows have been labeled by both raters.")
        log("  Fill human_label_rater_A and human_label_rater_B columns.")
        log("  Then adjudicate disagreements into adjudicated_label column.")
        log("  Then re-run this script.")
        LOG_PATH.write_text("\n".join(lines), encoding="utf-8")
        return

    # Cohen's kappa
    ra = labels_df["human_label_rater_A"].astype(int).tolist()
    rb = labels_df["human_label_rater_B"].astype(int).tolist()
    kappa = cohen_kappa(ra, rb)
    agree = np.mean(np.array(ra) == np.array(rb))
    log(f"Inter-rater Agreement:")
    log(f"  Raw agreement: {agree*100:.1f}%")
    log(f"  Cohen's kappa: {kappa:.4f}")
    if kappa < 0.60:
        log("  WARNING: Kappa < 0.60 (fair-to-moderate agreement). Adjudication is especially important.")
    log()

    # Use adjudicated labels if filled, else use Rater A (and log)
    adj_filled = labels_df["adjudicated_label"].notna() & (labels_df["adjudicated_label"].astype(str).str.strip() != "")
    if adj_filled.sum() == len(labels_df):
        y_true = labels_df["adjudicated_label"].astype(int).values
        label_source = "adjudicated"
    else:
        log(f"WARNING: adjudicated_label not fully filled ({adj_filled.sum()}/{len(labels_df)}).")
        log("  Using Rater A labels as fallback. Adjudicate disagreements for final results.")
        y_true = labels_df["human_label_rater_A"].astype(int).values
        label_source = "rater_A_only"
    log(f"Label source: {label_source}")
    log(f"  Positive (vague): {y_true.sum()} ({y_true.sum()/len(y_true)*100:.1f}%)")
    log()

    # Load batch3 original to get text for fresh detection
    batch3_orig = pd.read_csv(BATCH3_ORIG_PATH)
    # Align by id (labels_df has 1-indexed id matching batch3_orig index+1)
    texts = batch3_orig["text"].tolist()
    if len(texts) != len(y_true):
        log(f"ERROR: batch3 orig has {len(texts)} rows but label sheet has {len(y_true)} rows. Check alignment.")
        return

    # Run CURRENT detector fresh
    sys.path.insert(0, str(BASE / "src"))
    log("Running current detector on Batch 3 texts (FROZEN detector state)...")
    from analysis.vagueness.vagueness_combined import analyze_combined_vagueness
    y_pred = []
    sources = []
    for text in texts:
        result = analyze_combined_vagueness(text)
        y_pred.append(1 if result.is_flagged_vague else 0)
        sources.append(result.flag_source)
    y_pred = np.array(y_pred)

    log(f"  Model positive count: {y_pred.sum()} ({y_pred.sum()/len(y_pred)*100:.1f}%)")
    log()

    # Metrics
    prec, rec, f1, _ = precision_recall_fscore_support(y_true, y_pred, average="binary", zero_division=0)
    acc = float(np.mean(y_true == y_pred))
    auc = roc_auc_score(y_true, y_pred) if len(set(y_true)) == 2 else float("nan")
    f1_ci = bootstrap_f1_ci(y_true, y_pred)

    log("## HELD-OUT BATCH 3 RESULTS (detector frozen before labeling)")
    log(f"  N = {len(y_true)}")
    log(f"  Precision: {prec:.4f}")
    log(f"  Recall:    {rec:.4f}")
    log(f"  F1:        {f1:.4f}  95% CI [{f1_ci[0]:.4f}, {f1_ci[1]:.4f}]")
    log(f"  AUC-ROC:   {auc:.4f}")
    log(f"  Accuracy:  {acc:.4f}")
    log()
    log(classification_report(y_true, y_pred, target_names=["not_vague", "vague"], zero_division=0))

    cm = confusion_matrix(y_true, y_pred)
    log("Confusion matrix:")
    log(f"  TN={cm[0,0]}, FP={cm[0,1]}, FN={cm[1,0]}, TP={cm[1,1]}")
    log()

    # Load dev set metrics for comparison
    log("## DEV SET RESULTS (for comparison, NOT headline)")
    try:
        dev_dfs = []
        for p in [BATCH12_PATH, BATCH12B_PATH]:
            if p.exists():
                dev_dfs.append(pd.read_csv(p))
        dev_df = pd.concat(dev_dfs)
        dev_df = dev_df.dropna(subset=["human_label"])
        dev_df["human_label"] = dev_df["human_label"].astype(int)
        dev_preds = []
        for text in dev_df["text"]:
            result = analyze_combined_vagueness(text)
            dev_preds.append(1 if result.is_flagged_vague else 0)
        dev_y_true = dev_df["human_label"].values
        dev_y_pred = np.array(dev_preds)
        _, _, dev_f1, _ = precision_recall_fscore_support(dev_y_true, dev_y_pred, average="binary", zero_division=0)
        dev_auc = roc_auc_score(dev_y_true, dev_y_pred) if len(set(dev_y_true)) == 2 else float("nan")
        log(f"  Dev set (N={len(dev_y_true)}): F1={dev_f1:.4f}, AUC={dev_auc:.4f}")
        log(f"  IMPORTANT: Dev set was used during engine development (regex fixes, Signal 4).")
        log(f"  It is a DEVELOPMENT set number, not held-out.")
        log()
        log(f"  SUMMARY COMPARISON:")
        log(f"    Dev set F1:     {dev_f1:.4f}  (N={len(dev_y_true)}, development set)")
        log(f"    Held-out F1:    {f1:.4f}  (N={len(y_true)}, 95% CI [{f1_ci[0]:.4f}, {f1_ci[1]:.4f}])")
        log(f"    Direction: {'improvement' if f1 >= dev_f1 else 'degradation'} on held-out vs dev")
    except Exception as e:
        log(f"  Could not load dev set: {e}")

    # Save
    results = {
        "git_head": "be9fdb9f6cbba33ca99729e3fcd61e76a37b7dc6",
        "n_batch3": int(len(y_true)),
        "label_source": label_source,
        "inter_rater_kappa": float(kappa),
        "inter_rater_agreement": float(agree),
        "precision": float(prec),
        "recall": float(rec),
        "f1": float(f1),
        "f1_ci_lo": f1_ci[0],
        "f1_ci_hi": f1_ci[1],
        "auc_roc": float(auc),
        "accuracy": float(acc),
    }
    with open(RESULTS_JSON, "w") as f:
        json.dump(results, f, indent=2)
    log(f"Results saved to {RESULTS_JSON}")
    LOG_PATH.write_text("\n".join(lines), encoding="utf-8")
    log(f"Log saved to {LOG_PATH}")


if __name__ == "__main__":
    main()
