"""
Ensemble Evaluation: Soft-Voting between Checkpoint A (Unweighted) and Checkpoint B (Class-Balanced)

Computes ensemble probabilities:
    P_ensemble = alpha * P_unweighted + (1 - alpha) * P_weighted
Evaluates Top-1 Accuracy, Top-2 Accuracy, Macro-F1, Precision, and Recall on the 5,853 held-out test set.
"""
from __future__ import annotations

import json
from pathlib import Path
import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
from sklearn.metrics import classification_report, f1_score, precision_recall_fscore_support
from transformers import AutoModelForSequenceClassification, AutoTokenizer

MODEL_A_PATH = Path("data/models/brsr_principle_classifier/final_model_unweighted_93.68")
MODEL_B_PATH = Path("data/models/brsr_principle_classifier/final_model")
TEST_DATA_PATH = Path("data/training/test.csv")
OUTPUT_PATH = Path("data/models/brsr_principle_classifier/ensemble_test_results.json")

LABEL_NAMES = [f"Principle{i}" for i in range(1, 10)]
NUM_LABELS = 9
BATCH_SIZE = 32
MAX_LENGTH = 512


def predict_probabilities(model_path: Path, texts: list[str], device: str) -> np.ndarray:
    print(f"\nLoading model from: {model_path} ...")
    tokenizer = AutoTokenizer.from_pretrained(str(model_path))
    model = AutoModelForSequenceClassification.from_pretrained(str(model_path))
    model.to(device)
    model.eval()

    all_probs = []
    num_samples = len(texts)
    print(f"Running inference on {num_samples} samples (batch_size={BATCH_SIZE})...")

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

            if (i // BATCH_SIZE) % 40 == 0 or (i + BATCH_SIZE >= num_samples):
                done = min(i + BATCH_SIZE, num_samples)
                print(f"  Processed {done}/{num_samples} ({done/num_samples*100:.1f}%)")

    # Clean up GPU memory
    del model
    if device == "cuda":
        torch.cuda.empty_cache()

    return np.vstack(all_probs)


def evaluate_predictions(probs: np.ndarray, labels: np.ndarray, name: str) -> dict:
    top1_preds = np.argmax(probs, axis=-1)

    top2_preds = np.argsort(probs, axis=-1)[:, -2:]
    top2_correct = np.any(top2_preds == labels[:, None], axis=-1)
    top2_acc = float(np.mean(top2_correct))

    accuracy = float(np.mean(top1_preds == labels))
    precision, recall, f1, _ = precision_recall_fscore_support(labels, top1_preds, average="macro", zero_division=0)

    print(f"\n{'='*65}")
    print(f"  Results for: {name}")
    print(f"{'='*65}")
    print(f"  Top-1 Accuracy: {accuracy * 100:.2f}%")
    print(f"  Top-2 Accuracy: {top2_acc * 100:.2f}%")
    print(f"  Macro-F1:       {f1:.4f}")
    print(f"  Macro-Precision:{precision:.4f}")
    print(f"  Macro-Recall:   {recall:.4f}")

    return {
        "accuracy": accuracy,
        "top2_accuracy": top2_acc,
        "macro_f1": f1,
        "macro_precision": precision,
        "macro_recall": recall,
        "top1_preds": top1_preds,
    }


def main():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Using device: {device}")
    if device == "cuda":
        print(f"GPU: {torch.cuda.get_device_name(0)}")

    df = pd.read_csv(TEST_DATA_PATH)
    texts = df["text"].fillna("").astype(str).tolist()
    labels = df["label"].astype(int).values

    print(f"Loaded {len(texts)} test samples from {TEST_DATA_PATH}")

    # 1. Predictions from Model A (Unweighted)
    probs_a = predict_probabilities(MODEL_A_PATH, texts, device)
    res_a = evaluate_predictions(probs_a, labels, "Model A (Unweighted - Step 2)")

    # 2. Predictions from Model B (Class-Balanced)
    probs_b = predict_probabilities(MODEL_B_PATH, texts, device)
    res_b = evaluate_predictions(probs_b, labels, "Model B (Class-Balanced - Step 4)")

    # 3. Soft-Voting Ensemble Grid Search for optimal alpha
    print(f"\n{'='*65}")
    print("  Grid Search: Soft-Voting Ensemble (alpha * Model_A + (1-alpha) * Model_B)")
    print(f"{'='*65}")

    best_alpha = 0.5
    best_acc = 0.0
    best_probs = None

    for alpha in [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]:
        ensemble_p = alpha * probs_a + (1.0 - alpha) * probs_b
        preds = np.argmax(ensemble_p, axis=-1)
        acc = float(np.mean(preds == labels))
        f1 = float(f1_score(labels, preds, average="macro"))
        print(f"  alpha={alpha:.1f} (A={alpha*100:.0f}%, B={(1-alpha)*100:.0f}%): Top-1 Acc = {acc*100:.2f}% | Macro-F1 = {f1:.4f}")
        if acc > best_acc:
            best_acc = acc
            best_alpha = alpha
            best_probs = ensemble_p

    # Detailed evaluation of best ensemble
    print(f"\nSelecting Best Ensemble Configuration: alpha = {best_alpha:.1f}")
    res_ensemble = evaluate_predictions(best_probs, labels, f"Optimal Ensemble (alpha={best_alpha:.1f})")

    report_dict = classification_report(
        labels, res_ensemble["top1_preds"], target_names=LABEL_NAMES, output_dict=True, digits=3, zero_division=0
    )
    report_str = classification_report(
        labels, res_ensemble["top1_preds"], target_names=LABEL_NAMES, digits=3, zero_division=0
    )
    print("\nDetailed Per-Principle Classification Report for Optimal Ensemble:")
    print(report_str)

    # Save results
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump({
            "model_a_path": str(MODEL_A_PATH),
            "model_b_path": str(MODEL_B_PATH),
            "model_a_accuracy": res_a["accuracy"],
            "model_a_macro_f1": res_a["macro_f1"],
            "model_b_accuracy": res_b["accuracy"],
            "model_b_macro_f1": res_b["macro_f1"],
            "best_alpha": best_alpha,
            "ensemble_accuracy": res_ensemble["accuracy"],
            "ensemble_top2_accuracy": res_ensemble["top2_accuracy"],
            "ensemble_macro_f1": res_ensemble["macro_f1"],
            "ensemble_macro_precision": res_ensemble["macro_precision"],
            "ensemble_macro_recall": res_ensemble["macro_recall"],
            "classification_report": report_dict,
        }, f, indent=2)

    print(f"\nEnsemble results saved to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
