"""Finish the saved seed-42 train-only control using validation only.

This does not train, resume training, or open test.csv. It recovers the
five-epoch checkpoint left by the post-training LayerNorm assertion failure.
"""

from __future__ import annotations

import csv
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import torch
from transformers import (
    AutoConfig,
    AutoModelForSequenceClassification,
    AutoTokenizer,
    DataCollatorWithPadding,
    Trainer,
    TrainingArguments,
)


ROOT = Path(__file__).resolve().parents[2]
IMPROVE = ROOT / "results" / "improve"
MODEL_DIR = ROOT / "data" / "models" / "stage3_control_train_only_seed42"
RESULT = IMPROVE / "stage3_control_train_only_val.json"
LOGITS = IMPROVE / "stage3_control_train_only_val_logits.npz"
RECOVERED = MODEL_DIR / "best_model_recovered"
FAILURE = IMPROVE / "stage3_control_train_only_failure_P1-S3-CONTROL-20261019T143527079988Z.json"
RUN_ID = "P1-S3-RECOVER-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def load_helpers():
    path = IMPROVE / "stage3_control_validation.py"
    spec = importlib.util.spec_from_file_location("stage3_control_validation_helpers", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def selected_checkpoint():
    checkpoints = MODEL_DIR / "checkpoints"
    latest = checkpoints / "checkpoint-9325"
    state_file = latest / "trainer_state.json"
    if not state_file.is_file():
        raise FileNotFoundError(state_file)
    state = json.loads(state_file.read_text(encoding="utf-8"))
    if state["global_step"] != 9325:
        raise ValueError("Expected the completed five-epoch, 9325-step run")
    best = Path(state["best_model_checkpoint"])
    if best.resolve() != latest.resolve():
        raise ValueError("The completed run selected a different checkpoint")
    history = [x for x in state["log_history"] if "eval_macro_f1" in x]
    if len(history) != 5 or history[-1]["epoch"] != 5.0:
        raise ValueError("Expected all five validation epochs in Trainer state")
    if not np.isclose(state["best_metric"], max(x["eval_macro_f1"] for x in history)):
        raise ValueError("Best checkpoint metric differs from validation history")
    if not np.isclose(state["best_metric"], history[-1]["eval_macro_f1"]):
        raise ValueError("The selected epoch is not epoch five")
    for name in ("model.safetensors", "config.json", "tokenizer.json", "training_args.bin"):
        if not (best / name).is_file():
            raise FileNotFoundError(best / name)
    return best, state


def record_ledger(status, verdict, result_path):
    with (IMPROVE / "experiment_ledger.csv").open("a", encoding="utf-8", newline="") as handle:
        csv.writer(handle).writerow([
            RUN_ID,
            "Recover completed seed-42 train-only control after post-training format assertion failure",
            "Existing epoch-5 checkpoint; strict load/reload; validation prediction only; no training",
            verdict if status == "PASS" else "NOT RUN",
            "NOT RUN",
            verdict,
            status,
            result_path.relative_to(ROOT).as_posix(),
        ])


def main():
    if RESULT.exists() or LOGITS.exists() or RECOVERED.exists():
        raise FileExistsError("Recovery output exists; refusing overwrite or repeat")
    if not FAILURE.is_file():
        raise FileNotFoundError("Original post-training failure record is missing")
    original_failure = json.loads(FAILURE.read_text(encoding="utf-8"))
    if original_failure.get("error") != "Expected 50 selected-checkpoint LayerNorm aliases; got 0":
        raise ValueError("Original failure is not the verified checkpoint-format assertion")
    base = load_helpers()
    phase0 = json.loads(base.PHASE0_PATH.read_text(encoding="utf-8"))
    if phase0.get("status") != "PASS":
        raise ValueError("Frozen Phase 0 metadata did not pass")
    train = base.read_split("train", phase0)
    val = base.read_split("val", phase0)
    if set(train["cin"]) & set(val["cin"]):
        raise ValueError("Train and validation companies overlap")
    if (len(train), train["cin"].nunique(), len(val), val["cin"].nunique()) != (29834, 814, 6374, 175):
        raise ValueError("Frozen split sizes or company counts changed")
    del train

    source = base.MODEL_SOURCES["train-only"] / "model.safetensors"
    mlm = json.loads(base.MLM_RESULT_PATH.read_text(encoding="utf-8"))
    if mlm.get("status") != "PASS" or mlm.get("strict_reload", {}).get("status") != "PASS":
        raise ValueError("Train-only MLM base was not verified")
    if base.hash_file(source) != mlm["model_artifacts"]["model.safetensors"]["sha256"]:
        raise ValueError("Train-only MLM base weight hash changed")

    best, state = selected_checkpoint()
    config = AutoConfig.from_pretrained(str(best), local_files_only=True)
    if config.num_labels != 9:
        raise ValueError("Selected checkpoint is not the nine-principle classifier")
    model = AutoModelForSequenceClassification.from_config(config)
    selected = base.restore_selected_checkpoint(
        SimpleNamespace(state=SimpleNamespace(best_model_checkpoint=str(best)), model=model)
    )
    if selected["layernorm_aliases_remapped"] != 0 or selected["tensors_restored"] != 201:
        raise ValueError("Saved checkpoint format or tensor count changed")
    tokenizer = AutoTokenizer.from_pretrained(str(best), local_files_only=True)
    source_tokenizer = AutoTokenizer.from_pretrained(str(base.MODEL_SOURCES["train-only"]), local_files_only=True)
    if tokenizer.get_vocab() != source_tokenizer.get_vocab():
        raise ValueError("Checkpoint tokenizer differs from train-only MLM base")
    checkpoint_tokenizer_json = json.loads((best / "tokenizer.json").read_text(encoding="utf-8"))
    source_tokenizer_json = json.loads(
        (base.MODEL_SOURCES["train-only"] / "tokenizer.json").read_text(encoding="utf-8")
    )
    for field in ("model", "normalizer", "pre_tokenizer", "post_processor", "decoder", "added_tokens"):
        if checkpoint_tokenizer_json[field] != source_tokenizer_json[field]:
            raise ValueError(f"Checkpoint tokenizer {field} differs from train-only MLM base")

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA unavailable; refusing unexpected CPU inference")
    args = TrainingArguments(
        output_dir=str(MODEL_DIR / "recovery_predict"),
        per_device_eval_batch_size=8, fp16=True, report_to="none",
    )
    val_ds = base.TextDataset(val, tokenizer)
    predictor = Trainer(
        model=model, args=args, data_collator=DataCollatorWithPadding(tokenizer=tokenizer)
    )
    prediction = predictor.predict(val_ds)
    logits = np.asarray(prediction.predictions, dtype=np.float32)
    truth = val["label"].astype(int).to_numpy()
    cins = val["cin"].astype(str).to_numpy()
    sources = val["source"].astype(str).to_numpy()
    if logits.shape != (len(val), 9):
        raise ValueError(f"Unexpected validation logit shape: {logits.shape}")
    if not np.array_equal(np.asarray(prediction.label_ids, dtype=int), truth):
        raise ValueError("Validation predictions do not align with CSV rows")
    if not np.isfinite(logits).all():
        raise ValueError("Validation logits contain non-finite values")

    masks = {
        "full": np.ones(len(val), dtype=bool),
        "section_b": sources == "section_b",
        "section_c": sources == "section_c",
        "notes_principle": sources == "notes_principle",
        "section_b_plus_notes": np.isin(sources, ["section_b", "notes_principle"]),
    }
    scores = {name: base.summarize(logits[mask], truth[mask], cins[mask])
              for name, mask in masks.items()}
    strict_recovery = base.recover_best(best, RECOVERED, model, tokenizer)

    np.savez_compressed(
        LOGITS, row_index=np.arange(len(val)), cin=cins, source=sources,
        label=truth, logits=logits,
    )
    result = {
        "schema_version": 1,
        "run_id": RUN_ID,
        "phase": "PHASE_1_STAGE_3_MATCHED_CONTROL_VALIDATION_RECOVERY",
        "status": "PASS",
        "encoder": "train-only",
        "role": "LEAKAGE-CONTROL BASE; accuracy change is not an improvement claim",
        "label_provenance": "agreement with taxonomy-derived weak labels (partly AI-assisted mapping)",
        "original_failed_run_id": original_failure["run_id"],
        "original_failure_path": FAILURE.relative_to(ROOT).as_posix(),
        "training_reused": True,
        "new_training_steps": 0,
        "test_performance": "NOT RUN",
        "test_file_read": False,
        "train_rows": 29834, "train_cins": 814,
        "validation_rows": len(val), "validation_cins": val["cin"].nunique(),
        "train_csv_sha256": phase0["dataset_metadata"]["train"]["sha256"],
        "validation_csv_sha256": phase0["dataset_metadata"]["val"]["sha256"],
        "test_csv_sha256_reference_only": phase0["dataset_metadata"]["test"]["sha256"],
        "mlm_base_weight_sha256": base.hash_file(source),
        "selected_checkpoint": selected,
        "best_metric_during_training": state["best_metric"],
        "trainer_log_history": state["log_history"],
        "validation": scores,
        "validation_logits_path": LOGITS.relative_to(ROOT).as_posix(),
        "validation_logits_sha256": base.hash_file(LOGITS),
        "recovered_model_dir": RECOVERED.relative_to(ROOT).as_posix(),
        "strict_recovery": strict_recovery,
        "environment": base.metadata(),
        "recovery_script_sha256": base.hash_file(Path(__file__)),
        "control_script_after_fix_sha256": base.hash_file(IMPROVE / "stage3_control_validation.py"),
        "prereg_sha256": base.hash_file(IMPROVE / "prereg.md"),
        "completed_at_utc": base.utc_now(),
    }
    with RESULT.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, ensure_ascii=False, default=str)
        handle.write("\n")
    record_ledger("PASS", "LEAKAGE CONTROL; recovered validation-only metrics", RESULT)
    full = scores["full"]
    print(f"Stage 3 train-only control RECOVERED: N={full['n']}; CINs={full['unique_cins']}; no retraining")
    print(f"Validation Top-1={full['metrics']['top1']:.4f}; Top-2={full['metrics']['top2']:.4f}; macro-F1={full['metrics']['macro_f1']:.4f}")
    print(f"Selected checkpoint strict restore: {selected['status']}; aliases={selected['layernorm_aliases_remapped']}")
    print(f"Model save/reload: {strict_recovery['status']}")
    print(f"Results: {RESULT}")
    print("Test performance: NOT RUN")


if __name__ == "__main__":
    main()
