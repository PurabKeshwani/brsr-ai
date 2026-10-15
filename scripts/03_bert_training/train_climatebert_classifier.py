"""
Phase C — ClimateBERT Fine-Tuning for SEBI 9-Principle Classification (Technique 3)

Backbone: climatebert/distilroberta-base-climate-f (82M params)
- Pretrained specifically on climate, sustainability, and ESG corporate disclosure corpora.
- DistilRoBERTa architecture: ~25% faster than bert-base-uncased with lower VRAM consumption.
- Evaluates Top-1 Accuracy, Top-2 Accuracy, Macro-F1 on the 5,853 held-out test set.
"""
from __future__ import annotations

import json
from pathlib import Path
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.metrics import classification_report, f1_score, precision_recall_fscore_support
from sklearn.utils.class_weight import compute_class_weight
from torch.utils.data import Dataset
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    DataCollatorWithPadding,
    Trainer,
    TrainingArguments,
)

MODEL_OPTIONS = {
    "climatebert": {
        "hf_name": "climatebert/distilroberta-base-climate-f",
        "output_dir": Path("data/models/climatebert_principle_classifier"),
        "batch_size": 8,
        "lr": 3e-5,
    },
    "deberta": {
        "hf_name": "microsoft/deberta-v3-small",
        "output_dir": Path("data/models/deberta_principle_classifier"),
        "batch_size": 8,
        "lr": 3e-5,
    },
}

DATA_DIR = Path("data/training")
NUM_LABELS = 9
MAX_LENGTH = 512

LABEL_NAMES = [f"Principle{i}" for i in range(1, 10)]

GRAD_ACCUMULATION_STEPS = 2   # Effective batch size = 8 * 2 = 16
NUM_EPOCHS = 4
WEIGHT_DECAY = 0.01
WARMUP_STEPS = 300


class BRSRTextDataset(Dataset):
    def __init__(self, texts: list[str], labels: list[int], tokenizer):
        self.texts = [str(t) for t in texts]
        self.labels = [int(lbl) for lbl in labels]
        self.tokenizer = tokenizer

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        encoded = self.tokenizer(
            self.texts[idx],
            truncation=True,
            max_length=MAX_LENGTH,
            return_tensors=None,
        )
        encoded["labels"] = self.labels[idx]
        return encoded


class WeightedTrainer(Trainer):
    def __init__(self, class_weights=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.class_weights = class_weights

    
def compute_loss(
    self,
    model,
    inputs,
    return_outputs=False,
    num_items_in_batch=None,
):
    labels = inputs.get("labels")
    outputs = model(**inputs)
    logits = outputs.logits

    # Compute loss in FP32 for numerical stability
    logits = logits.float()
    labels = labels.view(-1).long()

    if self.class_weights is not None:
        weights = self.class_weights.to(
            device=logits.device,
            dtype=logits.dtype,
        )
        loss_fct = nn.CrossEntropyLoss(weight=weights)
    else:
        loss_fct = nn.CrossEntropyLoss()

    loss = loss_fct(
        logits.view(-1, self.model.config.num_labels),
        labels,
    )

    return (loss, outputs) if return_outputs else loss



def compute_metrics(eval_pred):
    logits, labels = eval_pred
    top1_preds = np.argmax(logits, axis=-1)

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


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Train ESG Principle Classifier with upgraded backbones")
    parser.add_argument(
        "--model",
        choices=["climatebert", "deberta"],
        default="climatebert",
        help="Backbone model choice: 'climatebert' (default) or 'deberta'",
    )
    args = parser.parse_args()

    cfg = MODEL_OPTIONS[args.model]
    model_name = cfg["hf_name"]
    output_dir = cfg["output_dir"]
    batch_size = cfg["batch_size"]
    learning_rate = cfg["lr"]

    print(f"CUDA available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"GPU: {torch.cuda.get_device_name(0)}")
        print(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")

    print(f"\n{'='*65}\nInitializing Selected Backbone ({args.model}): {model_name}\n{'='*65}")
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSequenceClassification.from_pretrained(
        model_name, num_labels=NUM_LABELS, problem_type="single_label_classification"
    )

    train_texts, train_labels = load_split("train")
    val_texts, val_labels = load_split("val")
    test_texts, test_labels = load_split("test")

    print(f"Loaded dataset: {len(train_texts)} train | {len(val_texts)} val | {len(test_texts)} test")

    # Compute smoothed class weights
    raw_weights = compute_class_weight("balanced", classes=np.arange(NUM_LABELS), y=train_labels)
    smoothed_weights = np.sqrt(raw_weights)
    smoothed_weights = smoothed_weights / smoothed_weights.mean()
    class_weights_tensor = torch.tensor(smoothed_weights, dtype=torch.float)

    print("\nClass weights applied:")
    for i in range(NUM_LABELS):
        print(f"  P{i+1}: {smoothed_weights[i]:.3f}")

    train_dataset = BRSRTextDataset(train_texts, train_labels, tokenizer)
    val_dataset = BRSRTextDataset(val_texts, val_labels, tokenizer)
    test_dataset = BRSRTextDataset(test_texts, test_labels, tokenizer)

    data_collator = DataCollatorWithPadding(tokenizer=tokenizer)
    use_fp16 = False

    # Dynamic version check for eval_strategy vs evaluation_strategy
    import inspect
    sig = inspect.signature(TrainingArguments.__init__).parameters
    eval_arg_name = "eval_strategy" if "eval_strategy" in sig else "evaluation_strategy"
    strategy_args = {
        eval_arg_name: "epoch",
        "save_strategy": "epoch",
    }

    training_args = TrainingArguments(
        output_dir=str(output_dir / "checkpoints"),
        num_train_epochs=NUM_EPOCHS,
        per_device_train_batch_size=batch_size,
        per_device_eval_batch_size=batch_size * 2,
        gradient_accumulation_steps=GRAD_ACCUMULATION_STEPS,
        learning_rate=learning_rate,
        weight_decay=WEIGHT_DECAY,
        warmup_steps=WARMUP_STEPS,
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

    print(f"\nStarting {args.model.upper()} training on RTX 2050...")
    trainer.train()

    print(f"\n{'='*65}\nEvaluating {args.model.upper()} on Held-Out TEST Set (5,853 samples)\n{'='*65}")
    predictions = trainer.predict(test_dataset)
    logits = predictions.predictions
    preds = np.argmax(logits, axis=-1)

    top2_preds = np.argsort(logits, axis=-1)[:, -2:]
    top2_correct = np.any(top2_preds == np.array(test_labels)[:, None], axis=-1)
    top2_acc = float(np.mean(top2_correct))

    report_str = classification_report(test_labels, preds, target_names=LABEL_NAMES, digits=3, zero_division=0)
    report_dict = classification_report(test_labels, preds, target_names=LABEL_NAMES, output_dict=True, zero_division=0)
    print(report_str)

    macro_f1 = float(f1_score(test_labels, preds, average="macro"))
    accuracy = float(np.mean(preds == np.array(test_labels)))
    print(f"\nTop-1 Accuracy on held-out test set: {accuracy * 100:.2f}%")
    print(f"Top-2 Accuracy on held-out test set: {top2_acc * 100:.2f}%")
    print(f"Macro-averaged F1-Score:             {macro_f1:.4f}")

    output_dir.mkdir(parents=True, exist_ok=True)
    trainer.save_model(str(output_dir / "final_model"))
    tokenizer.save_pretrained(str(output_dir / "final_model"))

    with open(output_dir / "test_results.json", "w", encoding="utf-8") as f:
        json.dump({
            "model_name": model_name,
            "accuracy": accuracy,
            "top2_accuracy": top2_acc,
            "macro_f1": macro_f1,
            "classification_report": report_dict,
        }, f, indent=2)

    print(f"\nModel saved to: {output_dir / 'final_model'}")
    print(f"Results saved to: {output_dir / 'test_results.json'}")


if __name__ == "__main__":
    main()
