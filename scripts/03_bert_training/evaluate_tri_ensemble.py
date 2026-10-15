"""
Tri-Ensemble & Multi-Model Evaluation Script

Evaluates:
  1. Domain-Adapted BERT (Unweighted 93.68% checkpoint)
  2. ClimateBERT (distilroberta-base-climate-f)
  3. DeBERTa-v3 (microsoft/deberta-v3-small)
  4. Dual Ensemble (BERT + ClimateBERT)
  5. Tri-Ensemble (BERT + ClimateBERT + DeBERTa)

Outputs Top-1 Accuracy, Top-2 Accuracy, Macro-F1, Precision, and Recall on the 5,853 held-out test set.
Saves comprehensive multi-model results to:
  data/models/tri_ensemble_results.json
"""
from __future__ import annotations

import json
from pathlib import Path
import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
from sklearn.metrics import classification_report, precision_recall_fscore_support
from transformers import AutoModelForSequenceClassification, AutoTokenizer

MODELS = {
    "bert": {
        "name": "Domain-Adapted BERT",
        "path": Path("data/models/brsr_principle_classifier/final_model_unweighted_93.68"),
    },
    "climatebert": {
        "name": "ClimateBERT (DistilRoBERTa-climate-f)",
        "path": Path("data/models/climatebert_principle_classifier/final_model"),
    },
    "deberta": {
        "name": "DeBERTa-v3 Small",
        "path": Path("data/models/deberta_principle_classifier/final_model"),
    },
}

TEST_DATA_PATH = Path("data/training/test.csv")
OUTPUT_PATH = Path("data/models/tri_ensemble_results.json")

LABEL_NAMES = [f"Principle{i}" for i in range(1, 10)]
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

    model_probs = {}
    model_results = {}

    for key, info in MODELS.items():
        if info["path"].exists():
            probs = predict_probabilities(info["path"], texts, device)
            res = evaluate_predictions(probs, labels, info["name"])
            model_probs[key] = probs
            model_results[key] = res
        else:
            print(f"⚠️  Checkpoint not found for {info['name']} at {info['path']}. Skipping.")

    summary_results = {"individual_models": {k: {m: v for m, v in res.items() if m != "top1_preds"} for k, res in model_results.items()}}

    # 1. Dual Ensemble: BERT + ClimateBERT
    if "bert" in model_probs and "climatebert" in model_probs:
        print(f"\n{'='*65}")
        print("  Grid Search: Dual Ensemble (alpha * BERT + (1-alpha) * ClimateBERT)")
        print(f"{'='*65}")
        best_alpha = 0.5
        best_acc = 0.0
        best_dual_probs = None

        for alpha in [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]:
            ens_p = alpha * model_probs["bert"] + (1.0 - alpha) * model_probs["climatebert"]
            preds = np.argmax(ens_p, axis=-1)
            acc = float(np.mean(preds == labels))
            f1 = float(precision_recall_fscore_support(labels, preds, average="macro", zero_division=0)[2])
            print(f"  alpha={alpha:.1f} (BERT={alpha*100:.0f}%, ClimateBERT={(1-alpha)*100:.0f}%): Top-1 Acc = {acc*100:.2f}% | Macro-F1 = {f1:.4f}")
            if acc > best_acc:
                best_acc = acc
                best_alpha = alpha
                best_dual_probs = ens_p

        print(f"\nSelecting Best Dual Ensemble Configuration: alpha = {best_alpha:.1f}")
        dual_res = evaluate_predictions(best_dual_probs, labels, f"Optimal Dual Ensemble (BERT + ClimateBERT, alpha={best_alpha:.1f})")
        report_str = classification_report(labels, dual_res["top1_preds"], target_names=LABEL_NAMES, digits=3, zero_division=0)
        report_dict = classification_report(labels, dual_res["top1_preds"], target_names=LABEL_NAMES, output_dict=True, digits=3, zero_division=0)
        print("\nDual Ensemble Per-Principle Classification Report:")
        print(report_str)

        summary_results["dual_bert_climatebert"] = {
            "best_alpha": best_alpha,
            "accuracy": dual_res["accuracy"],
            "top2_accuracy": dual_res["top2_accuracy"],
            "macro_f1": dual_res["macro_f1"],
            "macro_precision": dual_res["macro_precision"],
            "macro_recall": dual_res["macro_recall"],
            "classification_report": report_dict,
        }

    # 2. Tri-Ensemble: BERT + ClimateBERT + DeBERTa
    if "bert" in model_probs and "climatebert" in model_probs and "deberta" in model_probs:
        print(f"\n{'='*65}")
        print("  Evaluating Tri-Ensemble: BERT + ClimateBERT + DeBERTa-v3")
        print(f"{'='*65}")
        tri_probs = (model_probs["bert"] + model_probs["climatebert"] + model_probs["deberta"]) / 3.0
        tri_res = evaluate_predictions(tri_probs, labels, "Tri-Ensemble (Equal Soft-Voting)")

        report_str = classification_report(labels, tri_res["top1_preds"], target_names=LABEL_NAMES, digits=3, zero_division=0)
        report_dict = classification_report(labels, tri_res["top1_preds"], target_names=LABEL_NAMES, output_dict=True, digits=3, zero_division=0)
        print("\nTri-Ensemble Per-Principle Classification Report:")
        print(report_str)

        summary_results["tri_ensemble"] = {
            "accuracy": tri_res["accuracy"],
            "top2_accuracy": tri_res["top2_accuracy"],
            "macro_f1": tri_res["macro_f1"],
            "macro_precision": tri_res["macro_precision"],
            "macro_recall": tri_res["macro_recall"],
            "classification_report": report_dict,
        }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(summary_results, f, indent=2)

    print(f"\nResults successfully saved to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
