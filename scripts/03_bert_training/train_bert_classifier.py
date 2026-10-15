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
        self.texts = texts
        self.labels = labels
        self.tokenizer = tokenizer

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        # Dynamic encoding: truncate to MAX_LENGTH but don't pad here (DataCollator pads per batch)
        encoded = self.tokenizer(
            self.texts[idx],
            truncation=True,
            max_length=MAX_LENGTH,
            return_tensors=None,
        )
        encoded["labels"] = self.labels[idx]
        return encoded


import torch.nn as nn
from sklearn.utils.class_weight import compute_class_weight


class WeightedTrainer(Trainer):
    def __init__(self, class_weights=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.class_weights = class_weights

    def compute_loss(self, model, inputs, return_outputs=False, num_items_in_batch=None):
        labels = inputs.get("labels")
        outputs = model(**inputs)
        logits = outputs.get("logits")
        if self.class_weights is not None:
            weights = self.class_weights.to(logits.device)
            loss_fct = nn.CrossEntropyLoss(weight=weights)
        else:
            loss_fct = nn.CrossEntropyLoss()
        loss = loss_fct(logits.view(-1, self.model.config.num_labels), labels.view(-1))
        return (loss, outputs) if return_outputs else loss


def compute_metrics(eval_pred):
    logits, labels = eval_pred
    top1_preds = np.argmax(logits, axis=-1)

    # Top-2 accuracy (true label in top 2 predictions)
    top2_preds = np.argsort(logits, axis=-1)[:, -2:]
    top2_correct = np.any(top2_preds == labels[:, None], axis=-1)
    top2_acc = float(np.mean(top2_correct))

    precision, recall, f1, _ = precision_recall_fscore_support(labels, top1_preds, average="macro", zero_division=0)
    acc = float(np.mean(top1_preds == labels))
    return {
        "accuracy": acc,
        "top2_accuracy": top2_acc,
        "macro_f1": f1,
        "macro_precision": precision,
        "macro_recall": recall,
    }


def load_split(name: str) -> tuple[list[str], list[int]]:
    df = pd.read_csv(DATA_DIR / f"{name}.csv")
    texts = df["text"].fillna("").astype(str).tolist()
    labels = df["label"].astype(int).tolist()
    return texts, labels


def train_with_model(model_name: str):
    print(f"\n{'='*60}\nAttempting training with: {model_name}\n{'='*60}")

    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSequenceClassification.from_pretrained(
        model_name, num_labels=NUM_LABELS, problem_type="single_label_classification",
    )

    train_texts, train_labels = load_split("train")
    val_texts, val_labels = load_split("val")

    # Step 4: Compute smoothed class weights to lift minority classes (P5, P7, P2)
    raw_weights = compute_class_weight("balanced", classes=np.arange(NUM_LABELS), y=train_labels)
    smoothed_weights = np.sqrt(raw_weights)
    smoothed_weights = smoothed_weights / smoothed_weights.mean()
    class_weights_tensor = torch.tensor(smoothed_weights, dtype=torch.float)
    print("\n[Step 4] Class-Balanced Weights applied:")
    for i in range(NUM_LABELS):
        print(f"  P{i+1}: weight = {smoothed_weights[i]:.3f}")

    train_dataset = BRSRTextDataset(train_texts, train_labels, tokenizer)
    val_dataset = BRSRTextDataset(val_texts, val_labels, tokenizer)

    from transformers import DataCollatorWithPadding
    data_collator = DataCollatorWithPadding(tokenizer=tokenizer)

    use_fp16 = torch.cuda.is_available()

    # Dynamic version check for eval_strategy vs evaluation_strategy
    import inspect
    sig = inspect.signature(TrainingArguments.__init__).parameters
    eval_arg_name = "eval_strategy" if "eval_strategy" in sig else "evaluation_strategy"
    strategy_args = {
        eval_arg_name: "epoch",
        "save_strategy": "epoch",
    }

    training_args = TrainingArguments(
        output_dir=str(OUTPUT_DIR / "checkpoints"),
        num_train_epochs=NUM_EPOCHS,
        per_device_train_batch_size=BATCH_SIZE,
        per_device_eval_batch_size=BATCH_SIZE * 2,
        gradient_accumulation_steps=GRAD_ACCUMULATION_STEPS,
        learning_rate=LEARNING_RATE,
        weight_decay=WEIGHT_DECAY,
        warmup_steps=300,
        lr_scheduler_type="cosine",
        load_best_model_at_end=True,
        metric_for_best_model="macro_f1",
        greater_is_better=True,
        save_total_limit=2,
        logging_steps=50,
        fp16=use_fp16,
        report_to="none",
        **strategy_args,
    )

    trainer = WeightedTrainer(
        class_weights=class_weights_tensor,
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        data_collator=data_collator,
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
    logits = predictions.predictions
    preds = np.argmax(logits, axis=-1)

    top2_preds = np.argsort(logits, axis=-1)[:, -2:]
    top2_correct = np.any(top2_preds == np.array(test_labels)[:, None], axis=-1)
    top2_acc = float(np.mean(top2_correct))

    report = classification_report(test_labels, preds, target_names=LABEL_NAMES, digits=3, zero_division=0)
    print(report)

    macro_f1 = f1_score(test_labels, preds, average="macro")
    accuracy = float(np.mean(preds == np.array(test_labels)))
    print(f"\nTop-1 Accuracy on held-out test set: {accuracy * 100:.2f}%")
    print(f"Top-2 Accuracy on held-out test set: {top2_acc * 100:.2f}%")
    print(f"Macro-averaged F1-Score on held-out test set: {macro_f1:.4f}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    trainer.save_model(str(OUTPUT_DIR / "final_model"))
    tokenizer.save_pretrained(str(OUTPUT_DIR / "final_model"))

    with open(OUTPUT_DIR / "test_results.json", "w") as f:
        json.dump({
            "model_used": used_model_name,
            "accuracy": float(accuracy),
            "top2_accuracy": float(top2_acc),
            "macro_f1": float(macro_f1),
            "classification_report": classification_report(
                test_labels, preds, target_names=LABEL_NAMES, output_dict=True, zero_division=0
            ),
        }, f, indent=2)

    print(f"\nModel saved to {OUTPUT_DIR / 'final_model'}")
    print(f"Results saved to {OUTPUT_DIR / 'test_results.json'}")


if __name__ == "__main__":
    main()
