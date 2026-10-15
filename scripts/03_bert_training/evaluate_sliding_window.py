"""
Technique 4: Sliding-Window Chunking for Long Disclosures (>512 Tokens)

Evaluates:
  1. Standard Truncation vs. Sliding-Window Chunking (window=512, stride=128)
  2. Aggregation strategies:
     - Mean Pooling: Mean probability across chunks
     - Max Pooling: Max probability per class across chunks (normalized)
  3. Applied to:
     - BERT
     - ClimateBERT
     - Dual Ensemble (BERT + ClimateBERT, alpha=0.5)
  4. Specific sub-analysis on Long Disclosures (>250 words and >400 words)

Outputs comparison metrics and saves results to:
  data/models/sliding_window_results.json
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

BERT_PATH = Path("data/models/brsr_principle_classifier/final_model_unweighted_93.68")
CLIMATEBERT_PATH = Path("data/models/climatebert_principle_classifier/final_model")
TEST_DATA_PATH = Path("data/training/test.csv")
OUTPUT_PATH = Path("data/models/sliding_window_results.json")

LABEL_NAMES = [f"Principle{i}" for i in range(1, 10)]
NUM_LABELS = 9
WINDOW_SIZE = 512
STRIDE = 128


def predict_sliding_window_dual_pooling(
    model_path: Path,
    texts: list[str],
    device: str,
) -> tuple[np.ndarray, np.ndarray]:
    print(f"\nLoading model from: {model_path} ...")
    tokenizer = AutoTokenizer.from_pretrained(str(model_path))
    model = AutoModelForSequenceClassification.from_pretrained(str(model_path))
    model.to(device)
    model.eval()

    num_samples = len(texts)
    mean_probabilities = []
    max_probabilities = []

    print(f"Running sliding-window inference on {num_samples} samples (window={WINDOW_SIZE}, stride={STRIDE})...")

    with torch.no_grad():
        for idx in range(num_samples):
            text = texts[idx]
            encoded = tokenizer(
                text,
                truncation=True,
                max_length=WINDOW_SIZE,
                stride=STRIDE,
                return_overflowing_tokens=True,
                return_tensors="pt",
                padding=True,
            )

            model_inputs = {
                "input_ids": encoded["input_ids"].to(device),
                "attention_mask": encoded["attention_mask"].to(device),
            }
            if "token_type_ids" in encoded and "roberta" not in str(model_path).lower():
                model_inputs["token_type_ids"] = encoded["token_type_ids"].to(device)

            num_chunks = model_inputs["input_ids"].shape[0]

            if device == "cuda":
                with torch.amp.autocast(device_type="cuda", dtype=torch.float16):
                    outputs = model(**model_inputs)
            else:
                outputs = model(**model_inputs)

            probs = F.softmax(outputs.logits, dim=-1).cpu().numpy()  # [num_chunks, 9]

            if num_chunks == 1:
                mean_p = probs[0]
                max_p = probs[0]
            else:
                mean_p = np.mean(probs, axis=0)
                raw_max = np.max(probs, axis=0)
                max_p = raw_max / np.sum(raw_max)

            mean_probabilities.append(mean_p)
            max_probabilities.append(max_p)

            if (idx + 1) % 1000 == 0 or (idx + 1) == num_samples:
                print(f"  Processed {idx + 1}/{num_samples} ({((idx + 1)/num_samples)*100:.1f}%)")

    del model
    if device == "cuda":
        torch.cuda.empty_cache()

    return np.vstack(mean_probabilities), np.vstack(max_probabilities)


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
    word_counts = df["text"].fillna("").astype(str).apply(lambda x: len(x.split())).values

    long_mask_250 = word_counts > 250
    long_mask_400 = word_counts > 400

    print(f"Loaded {len(texts)} test samples from {TEST_DATA_PATH}")
    print(f"  Samples > 250 words: {np.sum(long_mask_250)} ({np.mean(long_mask_250)*100:.2f}%)")
    print(f"  Samples > 400 words: {np.sum(long_mask_400)} ({np.mean(long_mask_400)*100:.2f}%)")

    # 1. Sliding window inference on BERT
    print("\n" + "=" * 65)
    print("  [1/2] Inference on Domain-Adapted BERT (Sliding Window)")
    print("=" * 65)
    bert_mean, bert_max = predict_sliding_window_dual_pooling(BERT_PATH, texts, device)
    res_bert_mean = evaluate_predictions(bert_mean, labels, "BERT (Sliding Window - Mean Pooling)")
    res_bert_max = evaluate_predictions(bert_max, labels, "BERT (Sliding Window - Max Pooling)")

    # 2. Sliding window inference on ClimateBERT
    print("\n" + "=" * 65)
    print("  [2/2] Inference on ClimateBERT (Sliding Window)")
    print("=" * 65)
    climate_mean, climate_max = predict_sliding_window_dual_pooling(CLIMATEBERT_PATH, texts, device)
    res_climate_mean = evaluate_predictions(climate_mean, labels, "ClimateBERT (Sliding Window - Mean Pooling)")
    res_climate_max = evaluate_predictions(climate_max, labels, "ClimateBERT (Sliding Window - Max Pooling)")

    # 3. Dual Ensemble Comparison
    print("\n" + "=" * 65)
    print("  [Ensemble Comparison] Dual Ensemble with Sliding-Window")
    print("=" * 65)
    ensemble_mean = 0.5 * bert_mean + 0.5 * climate_mean
    ensemble_max = 0.5 * bert_max + 0.5 * climate_max

    res_ens_mean = evaluate_predictions(ensemble_mean, labels, "Dual Ensemble (Sliding Window - Mean Pooling)")
    res_ens_max = evaluate_predictions(ensemble_max, labels, "Dual Ensemble (Sliding Window - Max Pooling)")

    # Select best ensemble
    best_ens_name = "Mean Pooling" if res_ens_mean["accuracy"] >= res_ens_max["accuracy"] else "Max Pooling"
    best_ens_res = res_ens_mean if res_ens_mean["accuracy"] >= res_ens_max["accuracy"] else res_ens_max
    best_ens_probs = ensemble_mean if res_ens_mean["accuracy"] >= res_ens_max["accuracy"] else ensemble_max

    report_str = classification_report(labels, best_ens_res["top1_preds"], target_names=LABEL_NAMES, digits=3, zero_division=0)
    report_dict = classification_report(labels, best_ens_res["top1_preds"], target_names=LABEL_NAMES, output_dict=True, digits=3, zero_division=0)
    print(f"\nClassification Report for Best Dual Ensemble ({best_ens_name}):")
    print(report_str)

    # 4. Long Disclosures Sub-Analysis (>250 words)
    print("\n" + "=" * 65)
    print(f"  Long Disclosures Sub-Analysis (> 250 words, n={np.sum(long_mask_250)})")
    print("=" * 65)
    res_long_250 = evaluate_predictions(best_ens_probs[long_mask_250], labels[long_mask_250], f"Long Disclosures (>250 words, {best_ens_name})")

    # 5. Long Disclosures Sub-Analysis (>400 words)
    print("\n" + "=" * 65)
    print(f"  Very Long Disclosures Sub-Analysis (> 400 words, n={np.sum(long_mask_400)})")
    print("=" * 65)
    res_long_400 = evaluate_predictions(best_ens_probs[long_mask_400], labels[long_mask_400], f"Very Long Disclosures (>400 words, {best_ens_name})")

    # Save results
    results_payload = {
        "bert_mean": {k: v for k, v in res_bert_mean.items() if k != "top1_preds"},
        "bert_max": {k: v for k, v in res_bert_max.items() if k != "top1_preds"},
        "climate_mean": {k: v for k, v in res_climate_mean.items() if k != "top1_preds"},
        "climate_max": {k: v for k, v in res_climate_max.items() if k != "top1_preds"},
        "ensemble_mean": {k: v for k, v in res_ens_mean.items() if k != "top1_preds"},
        "ensemble_max": {k: v for k, v in res_ens_max.items() if k != "top1_preds"},
        "best_ensemble_strategy": best_ens_name,
        "best_ensemble_overall": {k: v for k, v in best_ens_res.items() if k != "top1_preds"},
        "classification_report": report_dict,
        "long_disclosures_250": {
            "n_samples": int(np.sum(long_mask_250)),
            **{k: v for k, v in res_long_250.items() if k != "top1_preds"},
        },
        "long_disclosures_400": {
            "n_samples": int(np.sum(long_mask_400)),
            **{k: v for k, v in res_long_400.items() if k != "top1_preds"},
        },
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(results_payload, f, indent=2)

    print(f"\nSliding window results successfully saved to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
