"""Evaluate the frozen Stage 4 rule-based detector on development batches 1+2.

This is not a held-out evaluation: batches 1 and 2 informed engine development,
and their label blinding is unconfirmed. The script fingerprints the detector
files before scoring and writes the freeze manifest used by Batch 3 evaluation.
Run from the repository root with the project's .venv-ml Python.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import date
from pathlib import Path

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

BATCH_PATHS = [
    BASE / "data/validation/vagueness_validation_sample.csv",
    BASE / "data/validation/vagueness_validation_sample_batch2.csv",
]
ENGINE_FILES = [
    SRC / "analysis/vagueness/vagueness_combined.py",
    SRC / "analysis/vagueness/vagueness_lexicon.py",
    SRC / "analysis/vagueness/vagueness_semantic.py",
]
FREEZE_PATH = BASE / "data/validation/stage4_detector_freeze.json"
RESULT_PATH = BASE / "results/audit/stage4_dev80_frozen_results.json"
EXPECTED_N = 80


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_freeze_manifest() -> dict:
    return {
        "freeze_id": "stage4-rule-detector-2026-10-18",
        "freeze_date": date.today().isoformat(),
        "detector_type": "rule-based text vagueness subdetector (lexicon + semantic); claim-vs-figure and assurance-gap not evaluated here; XGBoost excluded",
        "semantic_model": "all-mpnet-base-v2",
        "decision_rules": {
            "lexicon_evasion": "flag",
            "with_kpi_semantic_vague_similarity_min": 0.58,
            "with_kpi_vague_minus_quantified_margin_min": 0.15,
            "without_kpi_semantic_vague_similarity_min": 0.42,
            "without_kpi_semantic_requires_vague_gt_quantified": True,
            "long_text_word_count_gt": 80,
            "long_text_hedging_density_min": 0.005,
        },
        "source_sha256": {str(path.relative_to(BASE)): sha256(path) for path in ENGINE_FILES},
    }


def freeze_or_verify() -> dict:
    current = build_freeze_manifest()
    if FREEZE_PATH.exists():
        stored = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))
        if stored.get("source_sha256") != current["source_sha256"]:
            raise RuntimeError(
                "Detector source differs from the frozen Stage 4 version. "
                "Do not score until the change is reviewed; do not overwrite the freeze manifest."
            )
        return stored
    FREEZE_PATH.parent.mkdir(parents=True, exist_ok=True)
    FREEZE_PATH.write_text(json.dumps(current, indent=2), encoding="utf-8")
    return current


def main() -> None:
    freeze = freeze_or_verify()
    frames = []
    for batch_no, path in enumerate(BATCH_PATHS, start=1):
        if not path.exists():
            raise FileNotFoundError(path)
        df = pd.read_csv(path)
        if "human_label" not in df.columns or "text" not in df.columns:
            raise ValueError(f"{path} must contain text and human_label columns")
        if df["human_label"].isna().any():
            raise ValueError(f"{path} has {int(df['human_label'].isna().sum())} missing human labels")
        df["human_label"] = pd.to_numeric(df["human_label"], errors="raise").astype(int)
        if not set(df["human_label"].unique()).issubset({0, 1}):
            raise ValueError(f"{path} has labels outside 0/1")
        df["batch"] = batch_no
        frames.append(df)

    combined = pd.concat(frames, ignore_index=True)
    if len(combined) != EXPECTED_N:
        raise ValueError(f"Expected N={EXPECTED_N} across batches 1+2, found N={len(combined)}")
    normalized_text = combined["text"].fillna("").astype(str).str.strip()
    if normalized_text.duplicated().any():
        examples = normalized_text[normalized_text.duplicated(keep=False)].head(5).tolist()
        raise ValueError(f"Duplicate text across batches; resolve before scoring. Examples: {examples}")

    from analysis.vagueness.vagueness_combined import analyze_combined_vagueness

    y_true = combined["human_label"].to_numpy()
    y_pred = [int(analyze_combined_vagueness(text).is_flagged_vague) for text in combined["text"].fillna("").astype(str)]
    precision, recall, f1, _ = precision_recall_fscore_support(
        y_true, y_pred, average="binary", zero_division=0
    )
    accuracy = float(accuracy_score(y_true, y_pred))
    auc_binary = float(roc_auc_score(y_true, y_pred)) if len(set(y_true)) == 2 else None
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])

    result = {
        "freeze_id": freeze["freeze_id"],
        "freeze_source_sha256": freeze["source_sha256"],
        "n": len(combined),
        "n_by_batch": {str(i): int((combined["batch"] == i).sum()) for i in (1, 2)},
        "label_blinding": "unconfirmed; source CSVs contain model_flagged and flag_source",
        "evaluation_role": "development only; batches 1+2 informed engine development",
        "accuracy": accuracy,
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "auc_roc_binary_predictions": auc_binary,
        "auc_interpretation": "computed from hard 0/1 decisions; equals balanced accuracy and is not a continuous-score ROC AUC",
        "confusion_matrix_labels_0_1": cm.tolist(),
        "classification_report": classification_report(
            y_true, y_pred, target_names=["not_vague", "vague"], output_dict=True, zero_division=0
        ),
    }
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(json.dumps(result, indent=2), encoding="utf-8")

    print(f"Freeze verified: {freeze['freeze_id']}")
    print(f"N={len(combined)} (batch 1={result['n_by_batch']['1']}, batch 2={result['n_by_batch']['2']})")
    print("Role: DEVELOPMENT ONLY; label blinding unconfirmed")
    print(f"Accuracy={accuracy:.4f} Precision={precision:.4f} Recall={recall:.4f} F1={f1:.4f}")
    print(f"AUC from binary predictions={auc_binary} (equals balanced accuracy; not continuous-score AUC)")
    print(f"Confusion matrix [TN,FP;FN,TP]: {cm.tolist()}")
    print(f"Freeze manifest: {FREEZE_PATH}")
    print(f"Results: {RESULT_PATH}")


if __name__ == "__main__":
    main()
