"""Continue bert-base-uncased MLM on the frozen train-only BRSR corpus.

User-run training only. No validation or test company text, labels, or metrics
are read. The fixed two-epoch final checkpoint is saved and strictly reloaded.
"""

from __future__ import annotations

import csv
import hashlib
import importlib.metadata
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
IMPROVE = ROOT / "results" / "improve"
MANIFEST_PATH = IMPROVE / "train_only_mlm_corpus_manifest.json"
RESULT_PATH = IMPROVE / "train_only_mlm_training.json"
LEDGER = IMPROVE / "experiment_ledger.csv"
MODEL_DIR = ROOT / "data" / "models" / "domain_adapted_bert_train_only_v1"
FINAL_DIR = MODEL_DIR / "final_model"
BASE_MODEL = "bert-base-uncased"
BASE_REVISION = "86b5e0934494bd15c9632b12f734a8a67f723594"
SEED = 42
RUN_ID = "P1-TRAIN-ONLY-MLM-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_hash(file_path: Path) -> str:
    h = hashlib.sha256()
    with file_path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def git_output(*args: str) -> bytes:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, check=True).stdout


def append_ledger(status: str, verdict: str, result_path: Path = RESULT_PATH) -> None:
    with LEDGER.open("a", encoding="utf-8", newline="") as handle:
        csv.writer(handle).writerow(
            [
                RUN_ID,
                "Train-company-only MLM adaptation as leakage control",
                "bert-base-uncased; 2 epochs; mask=.15; LR=1e-5; seed=42",
                "NOT RUN",
                "NOT RUN",
                verdict,
                status,
                result_path.relative_to(ROOT).as_posix(),
            ]
        )


def verify_corpus() -> tuple[list[str], dict]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if manifest.get("status") != "PASS":
        raise ValueError("Train-only corpus manifest did not PASS")
    if manifest.get("selection_rule") != "saved legacy corpus sentence with current DB mask == train only":
        raise ValueError("Corpus selection rule changed")
    if manifest.get("validation_test_contributing_cins") != 0:
        raise ValueError("Validation/test CIN contributed to corpus")
    if manifest.get("exact_sentence_overlap_with_validation_or_test_db_text") != 0:
        raise ValueError("Corpus includes validation/test text")
    if manifest.get("contributing_cin_count", 0) <= 0:
        raise ValueError("No contributing train companies")
    corpus_path = ROOT / manifest["new_corpus_path"]
    if file_hash(corpus_path) != manifest["new_corpus_sha256"]:
        raise ValueError("Train-only corpus hash changed")
    lines = corpus_path.read_text(encoding="utf-8").splitlines()
    if len(lines) != manifest["new_corpus_unique_sentences"]:
        raise ValueError("Train-only corpus sentence count changed")
    if len(lines) != len(set(lines)) or any(not line for line in lines):
        raise ValueError("Train-only corpus has duplicate/blank lines")
    return lines, manifest


def compare_saved_model(runtime_model, loaded_model):
    import torch

    original = runtime_model.state_dict()
    restored = loaded_model.state_dict()
    original_keys = set(original)
    restored_keys = set(restored)
    if original_keys != restored_keys:
        missing = sorted(original_keys - restored_keys)
        unexpected = sorted(restored_keys - original_keys)
        raise RuntimeError(f"Strict reload key mismatch: missing={missing[:5]}, unexpected={unexpected[:5]}")
    checked_tensors = 0
    checked_elements = 0
    for key in sorted(original_keys):
        before = original[key].detach().cpu()
        after = restored[key].detach().cpu()
        if before.shape != after.shape or before.dtype != after.dtype or not torch.equal(before, after):
            raise RuntimeError(f"Strict reload tensor mismatch: {key}")
        checked_tensors += 1
        checked_elements += before.numel()
    return {"status": "PASS", "tensors_compared": checked_tensors, "elements_compared": checked_elements,
            "comparison": "torch.equal on every saved model state tensor"}


def run() -> dict:
    import torch
    from datasets import Dataset
    from huggingface_hub import hf_hub_download
    from transformers import (
        AutoModelForMaskedLM,
        AutoTokenizer,
        DataCollatorForLanguageModeling,
        Trainer,
        TrainingArguments,
        set_seed,
    )

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA unavailable; stopping before an unexpectedly long CPU run")
    lines, manifest = verify_corpus()
    set_seed(SEED)
    # The pinned snapshot can contain a dangling model.safetensors symlink
    # after cache cleanup. Download that exact revision before local loading.
    base_weight_path = Path(hf_hub_download(
        repo_id=BASE_MODEL, filename="model.safetensors", revision=BASE_REVISION,
    ))
    if not base_weight_path.is_file():
        base_weight_path = Path(hf_hub_download(
            repo_id=BASE_MODEL, filename="model.safetensors",
            revision=BASE_REVISION, force_download=True,
        ))
    if not base_weight_path.is_file():
        raise FileNotFoundError(f"Pinned base weight was not restored: {base_weight_path}")
    base_weight_sha256 = file_hash(base_weight_path)
    tokenizer = AutoTokenizer.from_pretrained(
        BASE_MODEL, revision=BASE_REVISION, local_files_only=True
    )
    model, initial_load_info = AutoModelForMaskedLM.from_pretrained(
        BASE_MODEL, revision=BASE_REVISION, local_files_only=True,
        output_loading_info=True
    )
    if initial_load_info.get("error_msgs"):
        raise RuntimeError(f"Base-model loading errors: {initial_load_info['error_msgs']}")
    dataset = Dataset.from_dict({"text": lines})

    def tokenize(batch):
        return tokenizer(batch["text"], truncation=True, max_length=256)

    tokenized = dataset.map(tokenize, batched=True, remove_columns=["text"])
    collator = DataCollatorForLanguageModeling(
        tokenizer=tokenizer, mlm=True, mlm_probability=0.15
    )
    args = TrainingArguments(
        output_dir=str(MODEL_DIR / "checkpoints"),
        num_train_epochs=2,
        per_device_train_batch_size=4,
        gradient_accumulation_steps=8,
        learning_rate=1e-5,
        warmup_steps=0.1,  # Transformers 5.15 accepts a [0,1) ratio here.
        lr_scheduler_type="linear",
        max_grad_norm=1.0,
        fp16=True,
        gradient_checkpointing=True,
        save_strategy="epoch",
        save_total_limit=2,
        logging_steps=50,
        dataloader_num_workers=0,
        seed=SEED,
        data_seed=SEED,
        report_to="none",
    )
    trainer = Trainer(model=model, args=args, train_dataset=tokenized, data_collator=collator)
    train_output = trainer.train(resume_from_checkpoint=False)
    FINAL_DIR.mkdir(parents=True, exist_ok=False)
    trainer.save_model(str(FINAL_DIR))
    tokenizer.save_pretrained(str(FINAL_DIR))

    loaded, reload_info = AutoModelForMaskedLM.from_pretrained(
        str(FINAL_DIR), local_files_only=True, output_loading_info=True
    )
    if any(reload_info.get(name) for name in ("mismatched_keys", "error_msgs")):
        raise RuntimeError(f"Saved checkpoint reload errors: {reload_info}")
    # Transformers may report a tied-weight alias as missing even when its
    # value was restored. The tensor-by-tensor comparison below is decisive.
    tensor_check = compare_saved_model(trainer.model, loaded)
    reloaded_tokenizer = AutoTokenizer.from_pretrained(str(FINAL_DIR), local_files_only=True)
    if tokenizer.get_vocab() != reloaded_tokenizer.get_vocab():
        raise RuntimeError("Tokenizer vocabulary changed after save/reload")

    artifacts = {}
    for file_path in sorted(FINAL_DIR.iterdir()):
        if file_path.is_file():
            artifacts[file_path.name] = {"bytes": file_path.stat().st_size, "sha256": file_hash(file_path)}
    diff = git_output("diff", "--no-ext-diff", "--no-textconv", "--binary", "HEAD")
    gpu = torch.cuda.get_device_properties(0)
    result = {
        "schema_version": 1,
        "run_id": RUN_ID,
        "phase": "PHASE_1_TRAIN_ONLY_MLM_ADAPTATION",
        "status": "PASS",
        "verdict": "LEAKAGE CONTROL; not an accuracy improvement",
        "validation_performance": "NOT RUN",
        "test_performance": "NOT RUN",
        "corpus_manifest_path": MANIFEST_PATH.relative_to(ROOT).as_posix(),
        "corpus_manifest_sha256": file_hash(MANIFEST_PATH),
        "corpus_sha256": manifest["new_corpus_sha256"],
        "corpus_sentences": len(lines),
        "contributing_train_cins": manifest["contributing_cin_count"],
        "excluded_validation_test_cin_count": 0,
        "base_model": BASE_MODEL,
        "base_model_revision": BASE_REVISION,
        "base_model_weight_sha256": base_weight_sha256,
        "base_model_weight_path": str(base_weight_path),
        "base_model_commit_hash": getattr(model.config, "_commit_hash", None),
        "initial_load_info": initial_load_info,
        "config": {
            "epochs": 2, "max_length": 256, "mlm_probability": 0.15,
            "microbatch": 4, "gradient_accumulation_steps": 8,
            "learning_rate": 1e-5, "warmup_ratio": 0.1,
            "fp16": True, "gradient_checkpointing": True,
            "dynamic_padding": True, "seed": SEED,
            "checkpoint_selection": "fixed final epoch; no validation/test text",
        },
        "train_output_metrics": train_output.metrics,
        "trainer_log_history": trainer.state.log_history,
        "model_dir": FINAL_DIR.relative_to(ROOT).as_posix(),
        "model_artifacts": artifacts,
        "strict_reload": {**tensor_check, "loading_info": reload_info,
                          "tokenizer_vocabulary_equal": True},
        "environment": {
            "python_executable": sys.executable,
            "python_version": platform.python_version(),
            "git_commit": git_output("rev-parse", "HEAD").decode("ascii").strip(),
            "tracked_diff_sha256": sha256(diff),
            "worktree_dirty": bool(git_output("status", "--porcelain")),
            "package_versions": {
                name: importlib.metadata.version(name)
                for name in ("torch", "transformers", "datasets", "accelerate", "safetensors", "tokenizers", "huggingface_hub")
            },
            "gpu": {"name": gpu.name, "total_memory_bytes": gpu.total_memory},
            "torch_cuda_version": torch.version.cuda,
        },
        "script_sha256": file_hash(Path(__file__)),
        "prereg_sha256": file_hash(IMPROVE / "prereg.md"),
        "completed_at_utc": utc_now(),
    }
    return result


def main() -> None:
    if RESULT_PATH.exists() or MODEL_DIR.exists():
        raise FileExistsError("MLM result/model directory already exists; refusing overwrite/resume")
    append_ledger("RUNNING", "RUNNING")
    try:
        result = run()
        with RESULT_PATH.open("x", encoding="utf-8") as handle:
            json.dump(result, handle, indent=2, ensure_ascii=False, default=str)
            handle.write("\n")
        append_ledger("PASS", result["verdict"])
        print(f"Train-only MLM: PASS; {result['corpus_sentences']} sentences, {result['contributing_train_cins']} train CINs")
        print(f"Strict model reload: {result['strict_reload']['status']}; tensors compared={result['strict_reload']['tensors_compared']}")
        print(f"Training runtime seconds: {result['train_output_metrics'].get('train_runtime')}")
        print(f"Model: {FINAL_DIR}")
        print(f"Results: {RESULT_PATH}")
        print("Validation/test performance: NOT RUN")
    except Exception as exc:
        failure = IMPROVE / f"train_only_mlm_failure_{RUN_ID}.json"
        with failure.open("x", encoding="utf-8") as handle:
            json.dump({"run_id": RUN_ID, "status": "FAIL", "error_type": type(exc).__name__,
                       "error": str(exc), "validation_performance": "NOT RUN",
                       "test_performance": "NOT RUN", "completed_at_utc": utc_now()}, handle, indent=2)
            handle.write("\n")
        append_ledger("FAIL", f"LEAKAGE CONTROL; {type(exc).__name__}", failure)
        print(f"Train-only MLM: FAIL — {type(exc).__name__}: {exc}")
        print(f"Failure: {failure}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
