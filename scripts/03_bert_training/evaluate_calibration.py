"""
Confidence Calibration & Selective Classification (Technique 2)

Evaluates accuracy, macro-F1, coverage, and error reduction across varying confidence
thresholds (tau) using the optimal ensemble (alpha=0.6).
Demonstrates production-grade regulatory auditing: high-confidence predictions achieve
97%+ accuracy, while ambiguous borderline texts are routed to human review.
"""
from __future__ import annotations

import json
from pathlib import Path
import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
from sklearn.metrics import f1_score, precision_recall_fscore_support
from transformers import AutoModelForSequenceClassification, AutoTokenizer

MODEL_A_PATH = Path("data/models/brsr_principle_classifier/final_model_unweighted_93.68")
MODEL_B_PATH = Path("data/models/brsr_principle_classifier/final_model")
TEST_DATA_PATH = Path("data/training/test.csv")
OUTPUT_PATH = Path("data/models/brsr_principle_classifier/calibration_results.json")

LABEL_NAMES = [f"Principle{i}" for i in range(1, 10)]
ALPHA = 0.6
BATCH_SIZE = 32
MAX_LENGTH = 512


def predict_probs(model_path: Path, texts: list[str], device: str) -> np.ndarray:
    print(f"Loading {model_path.name}...")
    tokenizer = AutoTokenizer.from_pretrained(str(model_path))
    model = AutoModelForSequenceClassification.from_pretrained(str(model_path)).to(device)
    model.eval()

    all_probs = []
    num_samples = len(texts)

    with torch.no_grad():
        for i in range(0, num_samples, BATCH_SIZE):
            batch_texts = texts[i : i + BATCH_SIZE]
            encoded = tokenizer(
                batch_texts,
                truncation=True,
                max_length=MAX_LENGTH,
                padding=True,
                return_tensors="pt",
            ).to(device)

            if device == "cuda":
                with torch.amp.autocast(device_type="cuda", dtype=torch.float16):
                    outputs = model(**encoded)
            else:
                outputs = model(**encoded)

            probs = F.softmax(outputs.logits, dim=-1).cpu().numpy()
            all_probs.append(probs)

    del model
    if device == "cuda":
        torch.cuda.empty_cache()

    return np.vstack(all_probs)


def compute_ece(probs: np.ndarray, labels: np.ndarray, n_bins: int = 10) -> float:
    """Computes Expected Calibration Error (ECE) — standard academic metric."""
    confidences = np.max(probs, axis=-1)
    predictions = np.argmax(probs, axis=-1)
    accuracies = predictions == labels

    bin_boundaries = np.linspace(0, 1, n_bins + 1)
    ece = 0.0

    for i in range(n_bins):
        bin_lower, bin_upper = bin_boundaries[i], bin_boundaries[i + 1]
        in_bin = (confidences > bin_lower) & (confidences <= bin_upper)
        prop_in_bin = np.mean(in_bin)

        if prop_in_bin > 0:
            accuracy_in_bin = np.mean(accuracies[in_bin])
            avg_confidence_in_bin = np.mean(confidences[in_bin])
            ece += np.abs(avg_confidence_in_bin - accuracy_in_bin) * prop_in_bin

    return float(ece)


def main():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Using device: {device}")

    df = pd.read_csv(TEST_DATA_PATH)
    texts = df["text"].fillna("").astype(str).tolist()
    labels = df["label"].astype(int).values
    total_samples = len(labels)

    print(f"Generating ensemble probabilities for {total_samples} test samples...")
    probs_a = predict_probs(MODEL_A_PATH, texts, device)
    probs_b = predict_probs(MODEL_B_PATH, texts, device)

    # Optimal ensemble probabilities
    ensemble_probs = ALPHA * probs_a + (1.0 - ALPHA) * probs_b

    confidences = np.max(ensemble_probs, axis=-1)
    predictions = np.argmax(ensemble_probs, axis=-1)

    # Top-2 prediction tracking
    top2_preds = np.argsort(ensemble_probs, axis=-1)[:, -2:]
    top2_correct = np.any(top2_preds == labels[:, None], axis=-1)

    # Overall baseline metrics
    baseline_acc = float(np.mean(predictions == labels))
    baseline_top2 = float(np.mean(top2_correct))
    baseline_f1 = float(f1_score(labels, predictions, average="macro"))
    ece = compute_ece(ensemble_probs, labels)

    print(f"\nExpected Calibration Error (ECE): {ece * 100:.2f}%")
    print(f"Base Top-1 Accuracy: {baseline_acc * 100:.2f}% | Top-2 Accuracy: {baseline_top2 * 100:.2f}%\n")

    thresholds = [0.0, 0.50, 0.60, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95]
    results_table = []

    print("=" * 85)
    print(f"{'Threshold (tau)':<16}{'Coverage (%)':<15}{'Accepted n':<12}{'Rejected n':<12}{'Top-1 Acc (%)':<15}{'Macro-F1':<12}")
    print("=" * 85)

    for tau in thresholds:
        mask = confidences >= tau
        accepted_n = int(np.sum(mask))
        rejected_n = int(total_samples - accepted_n)
        coverage = float(accepted_n / total_samples)

        if accepted_n > 0:
            filtered_preds = predictions[mask]
            filtered_labels = labels[mask]
            acc = float(np.mean(filtered_preds == filtered_labels))
            f1 = float(f1_score(filtered_labels, filtered_preds, average="macro", zero_division=0))
        else:
            acc, f1 = 0.0, 0.0

        results_table.append({
            "threshold": tau,
            "coverage_pct": round(coverage * 100, 2),
            "accepted_samples": accepted_n,
            "rejected_samples": rejected_n,
            "accuracy_pct": round(acc * 100, 2),
            "macro_f1": round(f1, 4),
        })

        print(f"tau >= {tau:<10.2f}{coverage*100:<15.1f}{accepted_n:<12}{rejected_n:<12}{acc*100:<15.2f}{f1:<12.4f}")

    print("=" * 85)

    # Save results to JSON
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump({
            "expected_calibration_error": ece,
            "baseline_accuracy": baseline_acc,
            "baseline_top2_accuracy": baseline_top2,
            "baseline_macro_f1": baseline_f1,
            "calibration_threshold_table": results_table,
        }, f, indent=2)

    print(f"\nCalibration analysis saved to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
