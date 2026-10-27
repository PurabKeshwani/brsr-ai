"""
TASK 2 — Stage 3 Company-Level Retrain
=======================================
Retrains Domain-Adapted BERT on data/training_company_split/ (0% company overlap).
Runs 5 seeds to get mean ± std. Evaluates ONCE on test.

Hyperparameter search is on VALIDATION macro-F1 only.
Test set is NEVER touched until the final chosen config.

Trial log: results/audit/stage3_trials.csv
Final results: results/audit/task2_company_retrain_results.json

Run from repo root:
  python results/audit/task2_company_level_retrain.py

IMPORTANT: This script uses data/training_company_split/{train,val,test}.csv
           which has 0% company overlap between all splits.
           
Arguments (environment variables):
  TASK2_SEEDS: comma-separated seeds (default: 42,1,7,99,2024)
  TASK2_EPOCHS: number of epochs (default: 5)
  TASK2_LR: learning rate (default: 2e-5)
"""
from __future__ import annotations

import csv
import json
import os
import sys
import time
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

BASE = Path("d:/brsr-ai-phase0-1/brsr-ai")
DATA_DIR = BASE / "data/training_company_split"
DOMAIN_ADAPTED_PATH = BASE / "data/models/domain_adapted_bert/final_model"
AUDIT_DIR = BASE / "results/audit"
OUTPUT_DIR = BASE / "data/models/brsr_company_split_classifier"
AUDIT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TRIALS_CSV = AUDIT_DIR / "stage3_trials.csv"
RESULTS_JSON = AUDIT_DIR / "task2_company_retrain_results.json"
LOG_PATH = AUDIT_DIR / "task2_company_retrain_log.txt"

NUM_LABELS = 9
LABEL_NAMES = [f"Principle{i}" for i in range(1, 10)]

# Config (can override with env vars)
SEEDS = [int(s) for s in os.environ.get("TASK2_SEEDS", "42,1,7,99,2024").split(",")]
NUM_EPOCHS = int(os.environ.get("TASK2_EPOCHS", "5"))
LEARNING_RATE = float(os.environ.get("TASK2_LR", "2e-5"))
MAX_LENGTH = 512
BATCH_SIZE = 4
GRAD_ACCUM = 4  # effective batch = 16

# Model to use
MODEL_NAME = str(DOMAIN_ADAPTED_PATH) if DOMAIN_ADAPTED_PATH.exists() else "bert-base-uncased"

lines: list[str] = []


def log(msg: str = "") -> None:
    print(msg)
    lines.append(msg)


# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------

class BRSRDataset(Dataset):
    def __init__(self, texts, labels, tokenizer):
        self.texts = texts
        self.labels = labels
        self.tokenizer = tokenizer

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        enc = self.tokenizer(
            self.texts[idx], truncation=True, max_length=MAX_LENGTH, return_tensors=None
        )
        enc["labels"] = self.labels[idx]
        return enc


class WeightedTrainer(Trainer):
    def __init__(self, class_weights=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.class_weights = class_weights

    def compute_loss(self, model, inputs, return_outputs=False, num_items_in_batch=None):
        labels = inputs.get("labels")
        outputs = model(**inputs)
        logits = outputs.get("logits")
        if self.class_weights is not None:
            loss_fct = nn.CrossEntropyLoss(weight=self.class_weights.to(logits.device))
        else:
            loss_fct = nn.CrossEntropyLoss()
        loss = loss_fct(logits.view(-1, NUM_LABELS), labels.view(-1))
        return (loss, outputs) if return_outputs else loss


def compute_metrics(eval_pred):
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=-1)
    top2 = np.argsort(logits, axis=-1)[:, -2:]
    top2_acc = float(np.mean(np.any(top2 == labels[:, None], axis=-1)))
    _, _, f1, _ = precision_recall_fscore_support(labels, preds, average="macro", zero_division=0)
    acc = float(np.mean(preds == labels))
    return {"accuracy": acc, "top2_accuracy": top2_acc, "macro_f1": f1}


def load_split(name: str):
    df = pd.read_csv(DATA_DIR / f"{name}.csv")
    return df["text"].fillna("").astype(str).tolist(), df["label"].astype(int).tolist()


# ---------------------------------------------------------------------------
# Single seed train+eval
# ---------------------------------------------------------------------------

def train_one_seed(seed: int, trial_rows: list) -> dict:
    log(f"\n{'='*70}")
    log(f"  SEED {seed} — Training on company-disjoint split")
    log(f"{'='*70}")

    import inspect
    torch.manual_seed(seed)
    np.random.seed(seed)

    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForSequenceClassification.from_pretrained(
        MODEL_NAME, num_labels=NUM_LABELS, problem_type="single_label_classification"
    )

    train_texts, train_labels = load_split("train")
    val_texts, val_labels = load_split("val")

    # Class weights
    raw_w = compute_class_weight("balanced", classes=np.arange(NUM_LABELS), y=train_labels)
    smooth_w = np.sqrt(raw_w) / np.sqrt(raw_w).mean()
    class_weights = torch.tensor(smooth_w, dtype=torch.float)

    train_ds = BRSRDataset(train_texts, train_labels, tokenizer)
    val_ds = BRSRDataset(val_texts, val_labels, tokenizer)
    collator = DataCollatorWithPadding(tokenizer=tokenizer)

    use_fp16 = torch.cuda.is_available()
    sig = inspect.signature(TrainingArguments.__init__).parameters
    eval_kwarg = "eval_strategy" if "eval_strategy" in sig else "evaluation_strategy"

    out_dir = OUTPUT_DIR / f"seed_{seed}"
    args = TrainingArguments(
        output_dir=str(out_dir / "checkpoints"),
        num_train_epochs=NUM_EPOCHS,
        per_device_train_batch_size=BATCH_SIZE,
        per_device_eval_batch_size=BATCH_SIZE * 2,
        gradient_accumulation_steps=GRAD_ACCUM,
        learning_rate=LEARNING_RATE,
        weight_decay=0.01,
        warmup_steps=300,
        lr_scheduler_type="cosine",
        load_best_model_at_end=True,
        metric_for_best_model="macro_f1",
        greater_is_better=True,
        save_total_limit=2,
        logging_steps=100,
        fp16=use_fp16,
        report_to="none",
        seed=seed,
        **{eval_kwarg: "epoch", "save_strategy": "epoch"},
    )

    trainer = WeightedTrainer(
        class_weights=class_weights,
        model=model,
        args=args,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        data_collator=collator,
        compute_metrics=compute_metrics,
    )

    t0 = time.time()
    trainer.train()
    elapsed = time.time() - t0
    log(f"  Training done in {elapsed/60:.1f} min")

    # Evaluate on VALIDATION (for trial selection)
    val_metrics = trainer.evaluate(BRSRDataset(val_texts, val_labels, tokenizer))
    log(f"  Val macro-F1: {val_metrics.get('eval_macro_f1', '?'):.4f}")

    # Save checkpoint for this seed
    trainer.save_model(str(out_dir / "best_model"))
    tokenizer.save_pretrained(str(out_dir / "best_model"))

    trial_row = {
        "seed": seed,
        "model": MODEL_NAME,
        "lr": LEARNING_RATE,
        "epochs": NUM_EPOCHS,
        "batch_eff": BATCH_SIZE * GRAD_ACCUM,
        "val_macro_f1": val_metrics.get("eval_macro_f1", float("nan")),
        "val_top1": val_metrics.get("eval_accuracy", float("nan")),
        "val_top2": val_metrics.get("eval_top2_accuracy", float("nan")),
    }
    trial_rows.append(trial_row)
    log(f"  Trial: {trial_row}")

    # Clean up GPU
    del model
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    return trial_row


# ---------------------------------------------------------------------------
# Final test evaluation (called ONCE with best model)
# ---------------------------------------------------------------------------

def evaluate_on_test(model_dir: Path) -> dict:
    log(f"\n{'='*70}")
    log("  FINAL TEST SET EVALUATION (called once)")
    log(f"  Model: {model_dir}")
    log(f"{'='*70}")

    tokenizer = AutoTokenizer.from_pretrained(str(model_dir))
    model = AutoModelForSequenceClassification.from_pretrained(str(model_dir))
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device)
    model.eval()

    test_texts, test_labels = load_split("test")
    import torch.nn.functional as F
    all_probs = []
    with torch.no_grad():
        for i in range(0, len(test_texts), BATCH_SIZE * 2):
            batch = test_texts[i: i + BATCH_SIZE * 2]
            enc = tokenizer(batch, truncation=True, max_length=MAX_LENGTH,
                            padding=True, return_tensors="pt").to(device)
            if device == "cuda":
                with torch.amp.autocast(device_type="cuda", dtype=torch.float16):
                    out = model(**enc)
            else:
                out = model(**enc)
            probs = F.softmax(out.logits, dim=-1).cpu().numpy()
            all_probs.append(probs)

    probs = np.vstack(all_probs)
    labels = np.array(test_labels)
    preds = np.argmax(probs, axis=-1)
    top2 = np.argsort(probs, axis=-1)[:, -2:]
    top2_acc = float(np.mean(np.any(top2 == labels[:, None], axis=-1)))
    top1_acc = float(np.mean(preds == labels))
    macro_f1 = float(f1_score(labels, preds, average="macro", zero_division=0))

    report_dict = classification_report(
        labels, preds, target_names=LABEL_NAMES, output_dict=True, zero_division=0
    )
    report_str = classification_report(
        labels, preds, target_names=LABEL_NAMES, digits=3, zero_division=0
    )

    log(f"\n  Top-1 Accuracy: {top1_acc*100:.2f}%")
    log(f"  Top-2 Accuracy: {top2_acc*100:.2f}%")
    log(f"  Macro-F1:       {macro_f1:.4f}")
    log(f"\n{report_str}")

    # Also evaluate on "near-dup removed" subset (TF-IDF sim < 0.90)
    # Load similarity scores from task1 if available
    sim_csv = AUDIT_DIR / "task1_similarity_buckets.csv"
    strict_results = None
    if sim_csv.exists():
        sim_df = pd.read_csv(sim_csv)
        test_df = pd.read_csv(DATA_DIR / "test.csv")
        # match by index (same order)
        if len(sim_df) == len(test_df):
            strict_mask = sim_df["tfidf_max_sim"].values < 0.90
            if strict_mask.sum() > 0:
                strict_top1 = float(np.mean(preds[strict_mask] == labels[strict_mask]))
                strict_top2 = float(np.mean(np.any(top2[strict_mask] == labels[strict_mask, None], axis=-1)))
                strict_f1 = float(f1_score(labels[strict_mask], preds[strict_mask], average="macro", zero_division=0))
                strict_results = {
                    "n": int(strict_mask.sum()),
                    "top1": strict_top1,
                    "top2": strict_top2,
                    "macro_f1": strict_f1,
                }
                log(f"\n  Strict subset (TF-IDF sim<0.90, n={strict_results['n']}):")
                log(f"    Top-1: {strict_top1*100:.2f}%, Top-2: {strict_top2*100:.2f}%, Macro-F1: {strict_f1:.4f}")

    del model
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    return {
        "top1": top1_acc,
        "top2": top2_acc,
        "macro_f1": macro_f1,
        "per_principle": report_dict,
        "strict_subset": strict_results,
    }


# ---------------------------------------------------------------------------
# Bootstrap CI (cluster-bootstrap by CIN)
# ---------------------------------------------------------------------------

def cluster_bootstrap_ci(model_dir: Path, n_boot: int = 2000) -> dict:
    log(f"\n  Computing cluster-bootstrap CI (n_boot={n_boot}, grouped by CIN)...")
    test_df = pd.read_csv(DATA_DIR / "test.csv")
    test_texts = test_df["text"].fillna("").astype(str).tolist()
    test_labels = test_df["label"].astype(int).values
    cins = test_df["cin"].values

    tokenizer = AutoTokenizer.from_pretrained(str(model_dir))
    model = AutoModelForSequenceClassification.from_pretrained(str(model_dir))
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device)
    model.eval()

    import torch.nn.functional as F
    all_probs = []
    with torch.no_grad():
        for i in range(0, len(test_texts), BATCH_SIZE * 2):
            batch = test_texts[i: i + BATCH_SIZE * 2]
            enc = tokenizer(batch, truncation=True, max_length=MAX_LENGTH,
                            padding=True, return_tensors="pt").to(device)
            if device == "cuda":
                with torch.amp.autocast(device_type="cuda", dtype=torch.float16):
                    out = model(**enc)
            else:
                out = model(**enc)
            all_probs.append(F.softmax(out.logits, dim=-1).cpu().numpy())

    del model
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    probs = np.vstack(all_probs)
    preds = np.argmax(probs, axis=-1)
    correct = (preds == test_labels).astype(float)

    # Cluster by CIN
    unique_cins = np.unique(cins)
    rng = np.random.default_rng(42)
    boot_top1 = []
    boot_f1 = []

    for _ in range(n_boot):
        sampled_cins = rng.choice(unique_cins, size=len(unique_cins), replace=True)
        idx = np.concatenate([np.where(cins == c)[0] for c in sampled_cins])
        boot_top1.append(correct[idx].mean())
        boot_f1.append(f1_score(test_labels[idx], preds[idx], average="macro", zero_division=0))

    ci_top1 = (np.percentile(boot_top1, 2.5), np.percentile(boot_top1, 97.5))
    ci_f1 = (np.percentile(boot_f1, 2.5), np.percentile(boot_f1, 97.5))
    log(f"  Bootstrap Top-1 95% CI: [{ci_top1[0]*100:.2f}%, {ci_top1[1]*100:.2f}%]")
    log(f"  Bootstrap Macro-F1 95% CI: [{ci_f1[0]:.4f}, {ci_f1[1]:.4f}]")

    return {
        "top1_ci_lo": ci_top1[0], "top1_ci_hi": ci_top1[1],
        "f1_ci_lo": ci_f1[0], "f1_ci_hi": ci_f1[1],
    }


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    log("=" * 80)
    log("TASK 2 — STAGE 3 COMPANY-LEVEL RETRAIN")
    log(f"Model: {MODEL_NAME}")
    log(f"Seeds: {SEEDS}")
    log(f"Epochs: {NUM_EPOCHS}, LR: {LEARNING_RATE}")
    log(f"Data dir: {DATA_DIR}")
    log("=" * 80)

    # Verify 0% overlap
    train_df = pd.read_csv(DATA_DIR / "train.csv")
    test_df = pd.read_csv(DATA_DIR / "test.csv")
    val_df = pd.read_csv(DATA_DIR / "val.csv")
    train_cins = set(train_df["cin"])
    val_cins = set(val_df["cin"])
    test_cins = set(test_df["cin"])
    assert not train_cins.intersection(val_cins), "Company overlap detected between train and validation!"
    assert not train_cins.intersection(test_cins), "Company overlap detected between train and test!"
    assert not val_cins.intersection(test_cins), "Company overlap detected between validation and test!"
    log(f"\nVerified: train={len(train_df)}, val={len(val_df)}, test={len(test_df)}")
    log(f"CIN overlap train∩test: 0 [PASS]")
    log()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    log(f"Device: {device}")
    if device == "cuda":
        log(f"GPU: {torch.cuda.get_device_name(0)}")
        log(f"VRAM: {torch.cuda.get_device_properties(0).total_memory/1e9:.1f} GB")

    # Train all seeds
    trial_rows = []
    seed_val_f1s = []
    successful_seeds = []

    for seed in SEEDS:
        try:
            trial = train_one_seed(seed, trial_rows)
            seed_val_f1s.append(trial["val_macro_f1"])
            successful_seeds.append(seed)
        except torch.cuda.OutOfMemoryError:
            log(f"  OOM on seed {seed} — skipping")
            torch.cuda.empty_cache()
        except Exception as e:
            log(f"  ERROR on seed {seed}: {e}")

    # Save trials CSV
    if trial_rows:
        pd.DataFrame(trial_rows).to_csv(TRIALS_CSV, index=False)
        log(f"\nTrials saved to {TRIALS_CSV}")

    if not seed_val_f1s:
        raise RuntimeError("No training seed completed successfully; no model can be selected.")

    # Pick best completed seed by validation macro-F1
    best_idx = int(np.argmax(seed_val_f1s))
    best_seed = successful_seeds[best_idx]
    best_val_f1 = seed_val_f1s[best_idx]
    log(f"\nBest seed: {best_seed} (val macro-F1={best_val_f1:.4f})")
    log(f"Val macro-F1 across seeds: {[f'{x:.4f}' for x in seed_val_f1s]}")
    log(f"Mean: {np.mean(seed_val_f1s):.4f} ± {np.std(seed_val_f1s):.4f}")

    # SINGLE test evaluation on best model
    best_model_dir = OUTPUT_DIR / f"seed_{best_seed}" / "best_model"
    test_results = evaluate_on_test(best_model_dir)

    # Bootstrap CI
    ci = cluster_bootstrap_ci(best_model_dir, n_boot=2000)

    # Save results
    results = {
        "git_head": "be9fdb9f6cbba33ca99729e3fcd61e76a37b7dc6",
        "data_dir": str(DATA_DIR),
        "model": MODEL_NAME,
        "seeds": SEEDS,
        "best_seed": best_seed,
        "val_f1_per_seed": seed_val_f1s,
        "val_f1_mean": float(np.mean(seed_val_f1s)),
        "val_f1_std": float(np.std(seed_val_f1s)),
        "test_top1": test_results["top1"],
        "test_top2": test_results["top2"],
        "test_macro_f1": test_results["macro_f1"],
        "test_top1_ci_lo": ci["top1_ci_lo"],
        "test_top1_ci_hi": ci["top1_ci_hi"],
        "test_f1_ci_lo": ci["f1_ci_lo"],
        "test_f1_ci_hi": ci["f1_ci_hi"],
        "strict_subset": test_results["strict_subset"],
        "per_principle": test_results["per_principle"],
        "comparison": {
            "old_segment_split_top1": 0.9383,
            "old_segment_split_top2": 0.9807,
            "old_dedup_top1": 0.9313,
            "new_company_disjoint_top1": test_results["top1"],
        }
    }

    with open(RESULTS_JSON, "w") as f:
        json.dump(results, f, indent=2)
    log(f"\nResults saved to {RESULTS_JSON}")

    # Save log
    LOG_PATH.write_text("\n".join(lines), encoding="utf-8")
    log(f"Log saved to {LOG_PATH}")

    # Final summary
    log("\n" + "=" * 70)
    log("TASK 2 SUMMARY (company-disjoint test)")
    log("=" * 70)
    log(f"  Top-1 Accuracy: {test_results['top1']*100:.2f}% (95% CI: [{ci['top1_ci_lo']*100:.2f}%, {ci['top1_ci_hi']*100:.2f}%])")
    log(f"  Top-2 Accuracy: {test_results['top2']*100:.2f}%")
    log(f"  Macro-F1:       {test_results['macro_f1']:.4f} (95% CI: [{ci['f1_ci_lo']:.4f}, {ci['f1_ci_hi']:.4f}])")
    log(f"  Val F1 ({len(seed_val_f1s)} completed seeds): {np.mean(seed_val_f1s):.4f} ± {np.std(seed_val_f1s):.4f}")
    log()
    log("  Compare to segment-split:")
    log(f"    Old Top-1 (segment-split):        93.83%")
    log(f"    Old Top-1 (exact-dedup subset):   93.13%")
    log(f"    New Top-1 (company-disjoint):      {test_results['top1']*100:.2f}% ← honest number")
    log()
    log("  The company-disjoint number is the correct number to report in the paper.")


if __name__ == "__main__":
    main()
