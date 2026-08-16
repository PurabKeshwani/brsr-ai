"""
Phase C — BERT Fine-Tuning for SEBI 9-Principle Classification

Trains a sequence classification head on top of a pre-trained BERT
encoder, using the weakly-supervised dataset built in
build_training_dataset.py (labels derived from XBRL's own PrincipleAxis
dimension, not manual annotation — see that script's docstring).

Hardware note: designed to run on a 4GB VRAM GPU (RTX 2050 class) via a
small batch size + gradient accumulation, falling back to
distilbert-base-uncased (66M params, ~40% smaller) if bert-base-uncased
runs out of memory. Both are tried automatically — see MODEL_CANDIDATES.

Usage:
    python scripts/train_bert_classifier.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import classification_report, f1_score, precision_recall_fscore_support
from torch.utils.data import Dataset
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    Trainer,
    TrainingArguments,
)

DATA_DIR = Path("data/training")
OUTPUT_DIR = Path("data/models/brsr_principle_classifier")
NUM_LABELS = 9
MAX_LENGTH = 512  # BERT's max — matches the report's stated design (long texts truncated, not sliding-window in this first version)

LABEL_NAMES = [f"Principle{i}" for i in range(1, 10)]

# Tried in order — bert-base-uncased first (matches the report's stated
# architecture), falls back to distilbert-base-uncased automatically if
# a CUDA out-of-memory error occurs during training on 4GB VRAM hardware.
# Domain-adapted checkpoint tried first (see scripts/domain_pretrain_bert.py
# for the MLM continued-pretraining that produced this) — falls back to
# vanilla bert-base-uncased if the local path doesn't exist, so this
# script still works even before domain-adaptation has been run.
DOMAIN_ADAPTED_PATH = Path("data/models/domain_adapted_bert/final_model")
MODEL_CANDIDATES = (
    [str(DOMAIN_ADAPTED_PATH), "distilbert-base-uncased"]
    if DOMAIN_ADAPTED_PATH.exists()
    else ["bert-base-uncased", "distilbert-base-uncased"]
)

BATCH_SIZE = 4               # small, tuned for 4GB VRAM
GRAD_ACCUMULATION_STEPS = 4  # effective batch size = 4 * 4 = 16, matching the report's stated batch size
LEARNING_RATE = 2e-5
NUM_EPOCHS = 4
WEIGHT_DECAY = 0.01


class BRSRTextDataset(Dataset):
    def __init__(self, texts: list[str], labels: list[int], tokenizer):
        self.encodings = tokenizer(texts, truncation=True, padding="max_length", max_length=MAX_LENGTH)
        self.labels = labels

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        item = {k: torch.tensor(v[idx]) for k, v in self.encodings.items()}
        # Explicitly force long/int64 dtype — if this ever silently became
        # float (e.g. via a pandas dtype quirk), HuggingFace auto-detects
        # "regression" problem_type and switches to MSELoss instead of
        # CrossEntropyLoss, which is almost certainly why the real training
        # run showed a flat, elevated loss (~8.9, vs the ~2.2 expected
        # baseline for 9-class random-guess cross-entropy) that never
        # improved across 4 full epochs.
        item["labels"] = torch.tensor(self.labels[idx], dtype=torch.long)
        return item


def compute_metrics(eval_pred):
    logits, labels = eval_pred
    predictions = np.argmax(logits, axis=-1)
    precision, recall, f1, _ = precision_recall_fscore_support(labels, predictions, average="macro", zero_division=0)
    return {"macro_f1": f1, "macro_precision": precision, "macro_recall": recall}


def load_split(name: str) -> tuple[list[str], list[int]]:
    df = pd.read_csv(DATA_DIR / f"{name}.csv")
    return df["text"].tolist(), df["label"].tolist()


def train_with_model(model_name: str):
    print(f"\n{'='*60}\nAttempting training with: {model_name}\n{'='*60}")

    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSequenceClassification.from_pretrained(
        model_name, num_labels=NUM_LABELS, problem_type="single_label_classification",
    )

    train_texts, train_labels = load_split("train")
    val_texts, val_labels = load_split("val")

    train_dataset = BRSRTextDataset(train_texts, train_labels, tokenizer)
    val_dataset = BRSRTextDataset(val_texts, val_labels, tokenizer)

    training_args = TrainingArguments(
        output_dir=str(OUTPUT_DIR / "checkpoints"),
        num_train_epochs=NUM_EPOCHS,
        per_device_train_batch_size=BATCH_SIZE,
        per_device_eval_batch_size=BATCH_SIZE,
        gradient_accumulation_steps=GRAD_ACCUMULATION_STEPS,
        learning_rate=LEARNING_RATE,
        weight_decay=WEIGHT_DECAY,
        warmup_steps=0.1,
        eval_strategy="epoch",
        save_strategy="epoch",
        # load_best_model_at_end=True,
        # metric_for_best_model="macro_f1",
        logging_steps=20,
        fp16=False,  # mixed precision — halves memory usage on GPU, critical for 4GB VRAM
        report_to="none",
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        compute_metrics=compute_metrics,
    )

    trainer.train()
    return trainer, tokenizer, model_name


def main():
    print(f"CUDA available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"GPU: {torch.cuda.get_device_name(0)}")
        print(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")

    trainer = None
    used_model_name = None

    for model_name in MODEL_CANDIDATES:
        try:
            trainer, tokenizer, used_model_name = train_with_model(model_name)
            break
        except torch.cuda.OutOfMemoryError:
            print(f"\n OUT OF MEMORY with {model_name} — trying next candidate...")
            torch.cuda.empty_cache()
            continue

    if trainer is None:
        print("\nAll model candidates failed with OOM. Consider reducing BATCH_SIZE further or MAX_LENGTH.")
        return

    print(f"\n{'='*60}\nFinal evaluation on TEST set (using {used_model_name})\n{'='*60}")
    test_texts, test_labels = load_split("test")
    test_dataset = BRSRTextDataset(test_texts, test_labels, tokenizer)

    predictions = trainer.predict(test_dataset)
    preds = np.argmax(predictions.predictions, axis=-1)

    report = classification_report(test_labels, preds, target_names=LABEL_NAMES, digits=3, zero_division=0)
    print(report)

    macro_f1 = f1_score(test_labels, preds, average="macro")
    print(f"\nMacro-averaged F1-Score on held-out test set: {macro_f1:.4f}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    trainer.save_model(str(OUTPUT_DIR / "final_model"))
    tokenizer.save_pretrained(str(OUTPUT_DIR / "final_model"))

    with open(OUTPUT_DIR / "test_results.json", "w") as f:
        json.dump({
            "model_used": used_model_name,
            "macro_f1": float(macro_f1),
            "classification_report": classification_report(
                test_labels, preds, target_names=LABEL_NAMES, output_dict=True, zero_division=0
            ),
        }, f, indent=2)

    print(f"\nModel saved to {OUTPUT_DIR / 'final_model'}")
    print(f"Results saved to {OUTPUT_DIR / 'test_results.json'}")


if __name__ == "__main__":
    main()