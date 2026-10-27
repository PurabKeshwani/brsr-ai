"""Exploratory comparison of the frozen Stage 4 detector with AI annotations.

This is not a human or independent-rater evaluation and must not be reported as
held-out human performance. It deliberately does not calculate Cohen's kappa.
Run from the repository root with the project's .venv-ml Python.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    precision_recall_fscore_support,
    roc_auc_score,
)

BASE = Path(__file__).resolve().parents[2]
SRC = BASE / "src"
sys.path.insert(0, str(SRC))

ANNOTATIONS_PATH = BASE / "data/labeling_sheets/stage4_batch3_ai_annotations.csv"
BATCH3_PATH = BASE / "data/validation/vagueness_validation_sample_batch3.csv"
FREEZE_PATH = BASE / "data/validation/stage4_detector_freeze.json"
RESULT_PATH = BASE / "results/audit/stage4_batch3_ai_comparison.json"
ENGINE_FILES = [
    SRC / "analysis/vagueness/vagueness_combined.py",
    SRC / "analysis/vagueness/vagueness_lexicon.py",
    SRC / "analysis/vagueness/vagueness_semantic.py",
]


def main() -> None:
    if not FREEZE_PATH.exists():
        raise FileNotFoundError(f"Frozen detector manifest not found: {FREEZE_PATH}")
    manifest = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))
    current_hashes = {
        str(path.relative_to(BASE)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in ENGINE_FILES
    }
    if current_hashes != manifest.get("source_sha256"):
        raise RuntimeError("Detector source differs from freeze manifest; refusing comparison.")

    annotations = pd.read_csv(ANNOTATIONS_PATH)
    batch3 = pd.read_csv(BATCH3_PATH)
    required = {"id", "ai_label", "annotation_source"}
    if not required.issubset(annotations.columns):
        raise ValueError(f"AI annotation file must contain columns: {sorted(required)}")
    if "text" not in batch3.columns:
        raise ValueError(f"Batch 3 file must contain a text column: {BATCH3_PATH}")
    if len(annotations) != 70 or len(batch3) != 70:
        raise ValueError(f"Expected 70 rows in annotations and Batch 3; got {len(annotations)} and {len(batch3)}")
    if annotations["id"].duplicated().any() or annotations["id"].astype(int).tolist() != list(range(1, 71)):
        raise ValueError("AI annotations must have unique IDs 1 through 70 in Batch 3 order.")
    labels = pd.to_numeric(annotations["ai_label"], errors="raise").astype(int)
    if not set(labels.unique()).issubset({0, 1}):
        raise ValueError("ai_label must contain only 0/1 values.")
    if annotations["annotation_source"].isna().any() or not annotations["annotation_source"].astype(str).str.contains("AI-generated", case=False).all():
        raise ValueError("Every annotation must retain explicit AI-generated provenance.")

    from analysis.vagueness.vagueness_combined import analyze_combined_vagueness

    y_true = labels.to_numpy()
    y_pred = np.array([
        int(analyze_combined_vagueness(str(text) if pd.notna(text) else "").is_flagged_vague)
        for text in batch3["text"]
    ])
    precision, recall, f1, _ = precision_recall_fscore_support(
        y_true, y_pred, average="binary", zero_division=0
    )
    auc_binary = float(roc_auc_score(y_true, y_pred)) if len(set(y_true)) == 2 else None
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    result = {
        "freeze_id": manifest.get("freeze_id"),
        "freeze_source_sha256": manifest.get("source_sha256"),
        "dataset": str(ANNOTATIONS_PATH.relative_to(BASE)),
        "n": len(y_true),
        "label_source": "AI-generated text-only annotations; not human raters or adjudicated ground truth",
        "evaluation_role": "exploratory AI-label comparison only; not held-out human evaluation",
        "cohen_kappa": None,
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "auc_roc_binary_predictions": auc_binary,
        "auc_interpretation": "hard 0/1 prediction AUC equals balanced accuracy; not continuous-score ROC AUC",
        "confusion_matrix_labels_0_1": cm.tolist(),
        "classification_report": classification_report(
            y_true, y_pred, labels=[0, 1], target_names=["not_vague", "vague"],
            output_dict=True, zero_division=0,
        ),
        "limitations": [
            "AI labels are not human labels and do not establish human inter-rater reliability.",
            "Do not report these metrics as human-held-out or gold-standard performance.",
            "The evaluated system is the text-vagueness subdetector, not the complete four-signal auditor.",
        ],
    }
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"Freeze verified: {manifest.get('freeze_id')}")
    print("Role: EXPLORATORY AI-LABEL COMPARISON ONLY; NOT human-held-out evaluation")
    print(f"N={len(y_true)}; AI vague labels={int(y_true.sum())}; detector flags={int(y_pred.sum())}")
    print(f"Accuracy={result['accuracy']:.4f} Precision={precision:.4f} Recall={recall:.4f} F1={f1:.4f}")
    print(f"AUC from binary predictions={auc_binary} (not continuous-score ROC AUC)")
    print(f"Confusion matrix [TN,FP;FN,TP]: {cm.tolist()}")
    print("Cohen's kappa: not applicable (only one AI annotation set)")
    print(f"Results: {RESULT_PATH}")


if __name__ == "__main__":
    main()
