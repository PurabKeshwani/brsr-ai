"""Matched seed-42 classifier controls on the frozen company validation split.

Run separately with --encoder train-only and --encoder legacy. This script
reads train.csv and val.csv only. It never evaluates test.csv. Both branches
use the same supervised recipe; the legacy branch is a transductive-exposure
diagnostic and cannot replace the new train-only base.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from safetensors.torch import load_file
from sklearn.metrics import f1_score
from sklearn.utils.class_weight import compute_class_weight
from torch.utils.data import Dataset
from transformers import (
    AutoConfig,
    AutoModelForSequenceClassification,
    AutoTokenizer,
    DataCollatorWithPadding,
    Trainer,
    TrainingArguments,
    set_seed,
)


ROOT = Path(__file__).resolve().parents[2]
IMPROVE = ROOT / "results" / "improve"
SPLIT_DIR = ROOT / "data" / "training_company_split"
PHASE0_PATH = IMPROVE / "phase0_setup.json"
MLM_RESULT_PATH = IMPROVE / "train_only_mlm_training.json"
LEDGER = IMPROVE / "experiment_ledger.csv"
MODEL_SOURCES = {
    "train-only": ROOT / "data" / "models" / "domain_adapted_bert_train_only_v1" / "final_model",
    "legacy": ROOT / "data" / "models" / "domain_adapted_bert" / "final_model",
}
LABEL_IDS = list(range(9))
SEED = 42
BOOTSTRAP_SEED = 4206
BOOTSTRAP_REPLICATES = 2000
RUN_ID = "P1-S3-CONTROL-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hash_file(file_path: Path) -> str:
    h = hashlib.sha256()
    with file_path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def git_output(*args: str) -> bytes:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, check=True).stdout


def metadata() -> dict:
    diff = git_output("diff", "--no-ext-diff", "--no-textconv", "--binary", "HEAD")
    gpu = torch.cuda.get_device_properties(0)
    return {
        "python_executable": sys.executable,
        "python_version": platform.python_version(),
        "git_commit": git_output("rev-parse", "HEAD").decode("ascii").strip(),
        "tracked_diff_sha256": hash_bytes(diff),
        "worktree_dirty": bool(git_output("status", "--porcelain")),
        "package_versions": {
            name: importlib.metadata.version(name)
            for name in ("torch", "transformers", "accelerate", "safetensors", "numpy", "pandas", "scikit-learn")
        },
        "gpu": {"name": gpu.name, "total_memory_bytes": gpu.total_memory},
        "torch_cuda_version": torch.version.cuda,
    }


def ledger(status: str, verdict: str, result_path: Path, encoder: str) -> None:
    with LEDGER.open("a", encoding="utf-8", newline="") as handle:
        csv.writer(handle).writerow(
            [
                RUN_ID,
                f"Matched seed-42 supervised validation control: {encoder} encoder",
                "5 epochs; LR=2e-5; sqrt class weights; best val macro-F1",
                "NOT RUN" if status == "RUNNING" else verdict,
                "NOT RUN",
                verdict,
                status,
                result_path.relative_to(ROOT).as_posix(),
            ]
        )


def read_split(name: str, phase0: dict) -> pd.DataFrame:
    file_path = SPLIT_DIR / f"{name}.csv"
    expected = phase0["dataset_metadata"][name]
    if hash_file(file_path) != expected["sha256"]:
        raise ValueError(f"Frozen {name} CSV hash mismatch")
    df = pd.read_csv(file_path, dtype={"cin": "string"})
    required = {"text", "label", "source", "cin"}
    if not required <= set(df.columns):
        raise ValueError(f"{name} CSV missing columns {sorted(required - set(df.columns))}")
    if len(df) != expected["rows"]:
        raise ValueError(f"Frozen {name} row count mismatch")
    if df["cin"].isna().any() or df["label"].isna().any():
        raise ValueError(f"{name} CSV contains missing CIN or label")
    if not set(df["label"].astype(int)) <= set(LABEL_IDS):
        raise ValueError(f"{name} CSV has label outside 0..8")
    df["cin"] = df["cin"].str.strip().str.upper()
    if (df["cin"].str.len() == 0).any():
        raise ValueError(f"{name} CSV contains blank CIN")
    df["text"] = df["text"].fillna("").astype(str)
    df["source"] = df["source"].fillna("").astype(str)
    return df


def alias_key(key: str) -> str:
    if "LayerNorm." in key and key.endswith(".gamma"):
        return key[:-len("gamma")] + "weight"
    if "LayerNorm." in key and key.endswith(".beta"):
        return key[:-len("beta")] + "bias"
    return key


def compare_state(a, b) -> dict:
    left = a.state_dict()
    right = b.state_dict()
    if set(left) != set(right):
        raise RuntimeError("State-dict key sets differ after save/reload")
    count = 0
    elements = 0
    for key in sorted(left):
        x = left[key].detach().cpu()
        y = right[key].detach().cpu()
        if x.shape != y.shape or x.dtype != y.dtype or not torch.equal(x, y):
            raise RuntimeError(f"Saved/reloaded tensor mismatch: {key}")
        count += 1
        elements += x.numel()
    return {"status": "PASS", "tensor_count": count, "element_count": elements}


def restore_selected_checkpoint(trainer) -> dict:
    """Override Trainer's automatic best load with strict alias-aware restore."""
    if not trainer.state.best_model_checkpoint:
        raise RuntimeError("Trainer did not select a validation checkpoint")
    file_path = Path(trainer.state.best_model_checkpoint) / "model.safetensors"
    if not file_path.is_file():
        raise FileNotFoundError(file_path)
    raw = load_file(str(file_path), device="cpu")
    remapped = {}
    alias_count = 0
    for key, tensor in raw.items():
        mapped = alias_key(key)
        if mapped in remapped:
            raise RuntimeError(f"Duplicate selected-checkpoint tensor: {mapped}")
        remapped[mapped] = tensor
        alias_count += mapped != key
    # Transformers may save either legacy gamma/beta aliases or canonical
    # weight/bias keys. Strict state-dict coverage below verifies both formats.
    if alias_count not in (0, 50):
        raise RuntimeError(f"Mixed/incomplete selected-checkpoint LayerNorm aliases: {alias_count}")
    trainer.model.load_state_dict(remapped, strict=True)
    loaded = trainer.model.state_dict()
    if set(loaded) != set(remapped):
        raise RuntimeError("Selected checkpoint key coverage changed")
    for key in loaded:
        if not torch.equal(loaded[key].detach().cpu(), remapped[key]):
            raise RuntimeError(f"Selected checkpoint tensor differs after restore: {key}")
    return {
        "status": "PASS",
        "checkpoint_path": file_path.relative_to(ROOT).as_posix(),
        "checkpoint_sha256": hash_file(file_path),
        "layernorm_aliases_remapped": alias_count,
        "tensors_restored": len(remapped),
    }


def load_encoder_strict(source_dir: Path):
    source_file = source_dir / "model.safetensors"
    if not source_file.is_file():
        raise FileNotFoundError(source_file)
    config = AutoConfig.from_pretrained(str(source_dir), local_files_only=True)
    config.num_labels = 9
    config.problem_type = "single_label_classification"
    config.id2label = {i: f"Principle{i+1}Member" for i in LABEL_IDS}
    config.label2id = {v: k for k, v in config.id2label.items()}
    model = AutoModelForSequenceClassification.from_config(config)
    source = load_file(str(source_file), device="cpu")
    target = model.state_dict()
    expected = {key for key in target if key.startswith("bert.") and ".pooler." not in key}
    loaded = set()
    alias_count = 0
    for key, tensor in source.items():
        if not key.startswith("bert.") or ".pooler." in key:
            continue
        mapped = alias_key(key)
        if mapped in loaded or mapped not in expected:
            raise RuntimeError(f"Duplicate or unexpected encoder tensor: {key} -> {mapped}")
        if target[mapped].shape != tensor.shape or target[mapped].dtype != tensor.dtype:
            raise RuntimeError(f"Encoder shape/dtype mismatch: {key} -> {mapped}")
        target[mapped] = tensor
        loaded.add(mapped)
        alias_count += mapped != key
    if loaded != expected:
        raise RuntimeError(f"Encoder tensor coverage incomplete: {len(expected-loaded)} missing")
    if alias_count != 50:
        raise RuntimeError(f"Expected 50 BERT LayerNorm alias remaps; got {alias_count}")
    model.load_state_dict(target, strict=True)
    loaded_state = model.state_dict()
    for key in expected:
        if not torch.equal(loaded_state[key].detach().cpu(), target[key]):
            raise RuntimeError(f"Encoder tensor failed strict comparison: {key}")
    del source, target
    return model, {
        "status": "PASS", "source_file": source_file.relative_to(ROOT).as_posix(),
        "source_sha256": hash_file(source_file), "encoder_tensors_loaded": len(loaded),
        "layernorm_aliases_remapped": alias_count,
        "newly_initialized_modules": ["bert.pooler", "classifier"],
        "comparison": "every source BERT tensor loaded with equal shape/dtype/value",
    }


class TextDataset(Dataset):
    def __init__(self, frame: pd.DataFrame, tokenizer):
        self.texts = frame["text"].tolist()
        self.labels = frame["label"].astype(int).tolist()
        self.tokenizer = tokenizer

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, index):
        encoded = self.tokenizer(self.texts[index], truncation=True, max_length=512)
        encoded["labels"] = self.labels[index]
        return encoded


class WeightedTrainer(Trainer):
    def __init__(self, class_weights, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.class_weights = class_weights

    def compute_loss(self, model, inputs, return_outputs=False, num_items_in_batch=None):
        labels = inputs["labels"]
        output = model(**inputs)
        logits = output.logits
        loss = nn.CrossEntropyLoss(weight=self.class_weights.to(logits.device))(
            logits.view(-1, 9), labels.view(-1)
        )
        return (loss, output) if return_outputs else loss


def metrics_from_eval(eval_pred) -> dict:
    logits, truth = eval_pred
    pred = np.asarray(logits).argmax(axis=1)
    top2 = np.argsort(logits, axis=1)[:, -2:]
    return {
        "accuracy": float(np.mean(pred == truth)),
        "top2_accuracy": float(np.mean(np.any(top2 == truth[:, None], axis=1))),
        "macro_f1": float(f1_score(truth, pred, labels=LABEL_IDS, average="macro", zero_division=0)),
    }


def summarize(logits: np.ndarray, truth: np.ndarray, cins: np.ndarray) -> dict:
    n = len(truth)
    if n == 0:
        return {"n": 0, "unique_cins": 0, "metrics": None, "ci95": None,
                "reason": "empty predeclared subset"}
    pred = np.asarray(logits).argmax(axis=1)
    top2 = np.argsort(logits, axis=1)[:, -2:]

    def score(index):
        t = truth[index]
        p = pred[index]
        return (
            float(np.mean(p == t)),
            float(np.mean(np.any(top2[index] == t[:, None], axis=1))),
            float(f1_score(t, p, labels=LABEL_IDS, average="macro", zero_division=0)),
        )

    point = score(np.arange(n))
    unique = np.unique(cins)
    indices = {cin: np.flatnonzero(cins == cin) for cin in unique}
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    samples = np.empty((BOOTSTRAP_REPLICATES, 3), dtype=float)
    for i in range(BOOTSTRAP_REPLICATES):
        chosen = rng.choice(unique, size=len(unique), replace=True)
        row_idx = np.concatenate([indices[cin] for cin in chosen])
        samples[i] = score(row_idx)
    bounds = np.quantile(samples, [0.025, 0.975], axis=0)
    names = ("top1", "top2", "macro_f1")
    return {
        "n": n,
        "unique_cins": len(unique),
        "support_by_principle": {f"P{i+1}": int(np.sum(truth == i)) for i in LABEL_IDS},
        "metrics": {name: point[j] for j, name in enumerate(names)},
        "ci95": {name: [float(bounds[0, j]), float(bounds[1, j])] for j, name in enumerate(names)},
        "ci_method": "2,000 percentile bootstrap resamples of CIN clusters, seed 4206",
        "valid_replicates": BOOTSTRAP_REPLICATES,
        "undefined_replicates": 0,
    }


def recover_best(raw_dir: Path, recovered_dir: Path, runtime_model, tokenizer) -> dict:
    raw_file = raw_dir / "model.safetensors"
    if not raw_file.is_file():
        raise FileNotFoundError(raw_file)
    raw = load_file(str(raw_file), device="cpu")
    remapped = {}
    alias_count = 0
    for key, tensor in raw.items():
        mapped = alias_key(key)
        if mapped in remapped:
            raise RuntimeError(f"Duplicate checkpoint tensor after alias remap: {mapped}")
        remapped[mapped] = tensor
        alias_count += mapped != key
    if alias_count not in (0, 50):
        raise RuntimeError(f"Mixed/incomplete classifier LayerNorm aliases: {alias_count}")
    config = AutoConfig.from_pretrained(str(raw_dir), local_files_only=True)
    verified = AutoModelForSequenceClassification.from_config(config)
    verified.load_state_dict(remapped, strict=True)
    runtime_check = compare_state(runtime_model, verified)
    recovered_dir.mkdir(parents=True, exist_ok=False)
    verified.save_pretrained(str(recovered_dir), safe_serialization=True)
    tokenizer.save_pretrained(str(recovered_dir))
    reloaded, info = AutoModelForSequenceClassification.from_pretrained(
        str(recovered_dir), local_files_only=True, output_loading_info=True
    )
    if info.get("mismatched_keys") or info.get("error_msgs"):
        raise RuntimeError(f"Recovered checkpoint reload errors: {info}")
    reload_check = compare_state(verified, reloaded)
    if tokenizer.get_vocab() != AutoTokenizer.from_pretrained(
        str(recovered_dir), local_files_only=True
    ).get_vocab():
        raise RuntimeError("Recovered tokenizer vocabulary mismatch")
    return {
        "status": "PASS",
        "raw_checkpoint_sha256": hash_file(raw_file),
        "layernorm_aliases_remapped": alias_count,
        "runtime_to_raw_tensor_check": runtime_check,
        "save_reload_tensor_check": reload_check,
        "reload_info": info,
        "tokenizer_vocabulary_equal": True,
        "recovered_weight_sha256": hash_file(recovered_dir / "model.safetensors"),
    }


def run(encoder: str, model_dir: Path, cache_path: Path) -> dict:
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA unavailable; refusing unexpectedly long CPU training")
    script_sha_start = hash_file(Path(__file__))
    prereg_sha_start = hash_file(IMPROVE / "prereg.md")
    phase0 = json.loads(PHASE0_PATH.read_text(encoding="utf-8"))
    if phase0.get("status") != "PASS":
        raise ValueError("Phase 0 setup did not PASS")
    train = read_split("train", phase0)
    val = read_split("val", phase0)
    if set(train["cin"]) & set(val["cin"]):
        raise ValueError("Train/validation CIN overlap")
    if len(set(train["cin"])) != 814 or len(set(val["cin"])) != 175:
        raise ValueError("Frozen train/validation company counts changed")
    source_dir = MODEL_SOURCES[encoder]
    source_sha_start = hash_file(source_dir / "model.safetensors")
    if encoder == "train-only":
        mlm = json.loads(MLM_RESULT_PATH.read_text(encoding="utf-8"))
        if mlm.get("status") != "PASS" or mlm.get("strict_reload", {}).get("status") != "PASS":
            raise ValueError("Train-only MLM checkpoint is not verified")
        if hash_file(source_dir / "model.safetensors") != mlm["model_artifacts"]["model.safetensors"]["sha256"]:
            raise ValueError("Train-only MLM model hash changed")

    set_seed(SEED)
    tokenizer = AutoTokenizer.from_pretrained(str(source_dir), local_files_only=True)
    model, encoder_load = load_encoder_strict(source_dir)
    y_train = train["label"].astype(int).to_numpy()
    raw_weights = compute_class_weight("balanced", classes=np.array(LABEL_IDS), y=y_train)
    weights = np.sqrt(raw_weights)
    weights /= weights.mean()
    class_weights = torch.tensor(weights, dtype=torch.float32)
    args = TrainingArguments(
        output_dir=str(model_dir / "checkpoints"),
        num_train_epochs=5,
        per_device_train_batch_size=4,
        per_device_eval_batch_size=8,
        gradient_accumulation_steps=4,
        learning_rate=2e-5,
        weight_decay=0.01,
        warmup_steps=300,
        lr_scheduler_type="cosine",
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="macro_f1",
        greater_is_better=True,
        save_total_limit=2,
        logging_steps=100,
        fp16=True,
        seed=SEED,
        data_seed=SEED,
        report_to="none",
    )
    train_ds = TextDataset(train, tokenizer)
    val_ds = TextDataset(val, tokenizer)
    trainer = WeightedTrainer(
        class_weights=class_weights, model=model, args=args,
        train_dataset=train_ds, eval_dataset=val_ds,
        data_collator=DataCollatorWithPadding(tokenizer=tokenizer),
        compute_metrics=metrics_from_eval,
    )
    train_output = trainer.train(resume_from_checkpoint=False)
    selected_restore = restore_selected_checkpoint(trainer)
    prediction = trainer.predict(val_ds)
    logits = np.asarray(prediction.predictions, dtype=np.float32)
    truth = val["label"].astype(int).to_numpy()
    cins = val["cin"].astype(str).to_numpy()
    sources = val["source"].astype(str).to_numpy()
    if logits.shape != (len(val), 9):
        raise ValueError(f"Unexpected validation logits shape: {logits.shape}")
    if not np.array_equal(np.asarray(prediction.label_ids, dtype=int), truth):
        raise ValueError("Predicted validation row order differs from CSV labels")
    if not np.isfinite(logits).all():
        raise ValueError("Validation logits contain non-finite values")
    np.savez_compressed(
        cache_path, row_index=np.arange(len(val)), cin=cins, source=sources,
        label=truth, logits=logits,
    )
    subsets = {
        "full": np.ones(len(val), dtype=bool),
        "section_b": sources == "section_b",
        "section_c": sources == "section_c",
        "notes_principle": sources == "notes_principle",
        "section_b_plus_notes": np.isin(sources, ["section_b", "notes_principle"]),
    }
    scores = {name: summarize(logits[mask], truth[mask], cins[mask]) for name, mask in subsets.items()}
    raw_best = model_dir / "best_model_raw"
    raw_best.mkdir(parents=True, exist_ok=False)
    trainer.save_model(str(raw_best))
    tokenizer.save_pretrained(str(raw_best))
    recovery = recover_best(raw_best, model_dir / "best_model_recovered", trainer.model, tokenizer)
    if hash_file(Path(__file__)) != script_sha_start or hash_file(IMPROVE / "prereg.md") != prereg_sha_start:
        raise RuntimeError("Script or preregistration changed during training")
    if hash_file(source_dir / "model.safetensors") != source_sha_start:
        raise RuntimeError("Encoder source weights changed during training")
    for split_name in ("train", "val"):
        if hash_file(SPLIT_DIR / f"{split_name}.csv") != phase0["dataset_metadata"][split_name]["sha256"]:
            raise RuntimeError(f"Frozen {split_name} CSV changed during training")
    result = {
        "schema_version": 1,
        "run_id": RUN_ID,
        "phase": "PHASE_1_STAGE_3_MATCHED_CONTROL_VALIDATION",
        "status": "PASS",
        "encoder": encoder,
        "role": "LEAKAGE-CONTROL BASE" if encoder == "train-only" else "LEGACY TRANSDUCTIVE-EXPOSURE COMPARATOR",
        "label_provenance": "agreement with taxonomy-derived weak labels (partly AI-assisted mapping)",
        "test_performance": "NOT RUN",
        "train_rows": len(train), "train_cins": train["cin"].nunique(),
        "validation_rows": len(val), "validation_cins": val["cin"].nunique(),
        "train_csv_sha256": phase0["dataset_metadata"]["train"]["sha256"],
        "validation_csv_sha256": phase0["dataset_metadata"]["val"]["sha256"],
        "test_csv_sha256_reference_only": phase0["dataset_metadata"]["test"]["sha256"],
        "test_file_read": False,
        "encoder_load": encoder_load,
        "config": {
            "seed": SEED, "epochs": 5, "learning_rate": 2e-5,
            "max_length": 512, "microbatch": 4, "gradient_accumulation": 4,
            "weight_decay": 0.01, "warmup_steps": 300,
            "lr_scheduler": "cosine", "fp16": True,
            "class_weights": {f"P{i+1}": float(weights[i]) for i in LABEL_IDS},
            "checkpoint_choice": "highest full-validation nine-class macro-F1 epoch",
        },
        "training_metrics": train_output.metrics,
        "best_model_checkpoint": trainer.state.best_model_checkpoint,
        "best_metric": trainer.state.best_metric,
        "selected_checkpoint_strict_restore": selected_restore,
        "trainer_log_history": trainer.state.log_history,
        "validation": scores,
        "validation_logits_path": cache_path.relative_to(ROOT).as_posix(),
        "validation_logits_sha256": hash_file(cache_path),
        "raw_model_dir": raw_best.relative_to(ROOT).as_posix(),
        "recovered_model_dir": (model_dir / "best_model_recovered").relative_to(ROOT).as_posix(),
        "strict_recovery": recovery,
        "environment": metadata(),
        "script_sha256": script_sha_start,
        "prereg_sha256": prereg_sha_start,
        "completed_at_utc": utc_now(),
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--encoder", choices=("train-only", "legacy"), required=True)
    args = parser.parse_args()
    encoder = args.encoder
    stem = "train_only" if encoder == "train-only" else "legacy"
    model_dir = ROOT / "data" / "models" / f"stage3_control_{stem}_seed42"
    result_path = IMPROVE / f"stage3_control_{stem}_val.json"
    cache_path = IMPROVE / f"stage3_control_{stem}_val_logits.npz"
    if model_dir.exists() or result_path.exists() or cache_path.exists():
        raise FileExistsError("Control run output exists; refusing overwrite/resume")
    ledger("RUNNING", "RUNNING", result_path, encoder)
    try:
        result = run(encoder, model_dir, cache_path)
        with result_path.open("x", encoding="utf-8") as handle:
            json.dump(result, handle, indent=2, ensure_ascii=False, default=str)
            handle.write("\n")
        ledger("PASS", f"val macro-F1={result['validation']['full']['metrics']['macro_f1']:.6f}", result_path, encoder)
        full = result["validation"]["full"]
        print(f"Stage 3 control {encoder}: PASS; N={full['n']}; CINs={full['unique_cins']}")
        print(f"Validation Top-1={full['metrics']['top1']:.4f}; Top-2={full['metrics']['top2']:.4f}; macro-F1={full['metrics']['macro_f1']:.4f}")
        print(f"Strict encoder load: {result['encoder_load']['status']}; aliases={result['encoder_load']['layernorm_aliases_remapped']}")
        print(f"Strict selected-checkpoint recovery: {result['strict_recovery']['status']}")
        print(f"Validation logits: {cache_path}")
        print(f"Results: {result_path}")
        print("Test performance: NOT RUN")
    except Exception as exc:
        failure = IMPROVE / f"stage3_control_{stem}_failure_{RUN_ID}.json"
        with failure.open("x", encoding="utf-8") as handle:
            json.dump({"run_id": RUN_ID, "encoder": encoder, "status": "FAIL",
                       "error_type": type(exc).__name__, "error": str(exc),
                       "test_performance": "NOT RUN", "completed_at_utc": utc_now()}, handle, indent=2)
            handle.write("\n")
        ledger("FAIL", type(exc).__name__, failure, encoder)
        print(f"Stage 3 control {encoder}: FAIL — {type(exc).__name__}: {exc}")
        print(f"Failure: {failure}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
