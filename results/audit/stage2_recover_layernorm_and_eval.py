"""Recover Trainer checkpoints whose LayerNorm gamma/beta keys were not remapped.

This is a technical repair/recheck of the already-observed Stage 2
concept-disjoint diagnostic. It does not train or tune either model.

Run from repository root with .venv-ml. The user runs this script; the
assistant does not run it.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import torch
from transformers import AutoConfig, AutoModelForSequenceClassification, AutoTokenizer

from stage2_concept_disjoint_eval import bootstrap_ci, infer, summarize, MODEL_SOURCE

BASE = Path(__file__).resolve().parents[2]
EVAL_CSV = BASE / "data" / "training_concept_disjoint" / "test_section_c_heldout_concepts.csv"
REPORT_IN = BASE / "results" / "audit" / "stage2_concept_disjoint_results.json"
REPORT_OUT = BASE / "results" / "audit" / "stage2_concept_disjoint_recovered_results.json"

MODELS = {
    "concept_disjoint": {
        "checkpoint": BASE / "data" / "models" / "brsr_concept_disjoint_classifier" / "seed_42" / "checkpoints" / "checkpoint-6270",
        "output": BASE / "data" / "models" / "brsr_concept_disjoint_classifier" / "seed_42" / "recovered_checkpoint_6270",
    },
    "full_concept_baseline": {
        "checkpoint": BASE / "data" / "models" / "brsr_company_split_classifier" / "seed_99" / "checkpoints" / "checkpoint-7460",
        "output": BASE / "data" / "models" / "brsr_company_split_classifier" / "seed_99" / "recovered_checkpoint_7460",
    },
}

EXPECTED_LABELS = 9
EXPECTED_LAYERNORM_ALIASES = 50  # 25 BERT LayerNorm modules x gamma/beta


def read_state_dict(checkpoint: Path) -> dict[str, torch.Tensor]:
    safe_file = checkpoint / "model.safetensors"
    bin_file = checkpoint / "pytorch_model.bin"
    if safe_file.is_file():
        from safetensors.torch import load_file

        state = load_file(str(safe_file), device="cpu")
    elif bin_file.is_file():
        try:
            state = torch.load(bin_file, map_location="cpu", weights_only=True)
        except TypeError:  # Older PyTorch in the user's venv
            state = torch.load(bin_file, map_location="cpu")
    else:
        raise FileNotFoundError(f"No model.safetensors or pytorch_model.bin in {checkpoint}")
    if isinstance(state, dict) and "state_dict" in state and isinstance(state["state_dict"], dict):
        state = state["state_dict"]
    if not isinstance(state, dict) or not state:
        raise ValueError(f"Checkpoint state dict is empty or invalid: {checkpoint}")
    return state


def recover_one(name: str, checkpoint: Path, output: Path) -> Path:
    if not checkpoint.is_dir():
        raise FileNotFoundError(f"Expected selected checkpoint not found: {checkpoint}")
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite existing recovered model: {output}")

    config = AutoConfig.from_pretrained(str(checkpoint), local_files_only=True)
    if int(config.num_labels) != EXPECTED_LABELS:
        raise ValueError(f"{name}: expected {EXPECTED_LABELS} labels, got {config.num_labels}")
    model = AutoModelForSequenceClassification.from_config(config)
    original = read_state_dict(checkpoint)

    remapped: dict[str, torch.Tensor] = {}
    alias_count = 0
    for key, value in original.items():
        new_key = key
        if "LayerNorm." in key and key.endswith(".gamma"):
            new_key = key[:-len("gamma")] + "weight"
            alias_count += 1
        elif "LayerNorm." in key and key.endswith(".beta"):
            new_key = key[:-len("beta")] + "bias"
            alias_count += 1
        if new_key in remapped:
            raise ValueError(f"{name}: duplicate key after remapping: {new_key}")
        remapped[new_key] = value

    if alias_count != EXPECTED_LAYERNORM_ALIASES:
        raise ValueError(
            f"{name}: expected exactly {EXPECTED_LAYERNORM_ALIASES} LayerNorm gamma/beta keys; found {alias_count}. "
            "Checkpoint format differs from the audited issue; refusing an unsafe guess."
        )

    # Strict loading proves every model parameter came from the selected checkpoint.
    model.load_state_dict(remapped, strict=True)
    output.mkdir(parents=True, exist_ok=False)
    model.save_pretrained(str(output), safe_serialization=True)

    # Use the same local tokenizer as the original model family.
    tokenizer = AutoTokenizer.from_pretrained(str(MODEL_SOURCE), local_files_only=True)
    tokenizer.save_pretrained(str(output))

    # Reload the serialized repair and compare every tensor to the loaded model.
    verified = AutoModelForSequenceClassification.from_pretrained(str(output), local_files_only=True)
    expected_sd = model.state_dict()
    actual_sd = verified.state_dict()
    if expected_sd.keys() != actual_sd.keys():
        raise RuntimeError(f"{name}: reloaded model parameter keys differ after save")
    for key in expected_sd:
        if not torch.equal(expected_sd[key].cpu(), actual_sd[key].cpu()):
            raise RuntimeError(f"{name}: serialized tensor mismatch after save: {key}")
    print(f"{name}: strict checkpoint load PASS; remapped {alias_count} LayerNorm aliases; save/reload PASS")
    del model, verified
    return output


def main() -> None:
    if not EVAL_CSV.is_file() or not REPORT_IN.is_file():
        raise FileNotFoundError("Existing concept-disjoint evaluation CSV or source report is missing")
    import pandas as pd

    df = pd.read_csv(EVAL_CSV, dtype={"cin": "string"})
    required = {"text", "label", "cin_norm", "concept", "source"}
    if not required.issubset(df.columns):
        raise ValueError(f"Evaluation CSV is missing columns: {sorted(required - set(df.columns))}")
    if len(df) != 1190 or df["source"].nunique() != 1 or df["source"].iloc[0] != "section_c":
        raise ValueError("Evaluation rows do not match the previously audited N=1190 Section C holdout")
    if int(df["cin_norm"].nunique()) != 174:
        raise ValueError("Evaluation CIN count differs from the previously audited 174 companies")

    recovered_paths = {}
    for name, spec in MODELS.items():
        recovered_paths[name] = recover_one(name, spec["checkpoint"], spec["output"])

    preds = {}
    metrics = {}
    for name, model_dir in recovered_paths.items():
        pred, top2 = infer(model_dir, df)
        preds[name] = pred
        metrics[name] = summarize(df, pred, top2)

    truth = df["label"].to_numpy(dtype=int)
    delta = (preds["concept_disjoint"] == truth).astype(float) - (preds["full_concept_baseline"] == truth).astype(float)
    delta_ci = bootstrap_ci(delta + 1.0, df["cin_norm"].to_numpy())
    if delta_ci is not None:
        delta_ci = [delta_ci[0] - 1.0, delta_ci[1] - 1.0]

    source_report = json.loads(REPORT_IN.read_text(encoding="utf-8"))
    result = {
        "evaluation": "Technical recovery and recheck of the already-observed Stage 2 concept-disjoint Section C diagnostic",
        "fresh_test": False,
        "n": int(len(df)),
        "unique_cins": int(df["cin_norm"].nunique()),
        "unique_heldout_concepts": int(df["concept"].nunique()),
        "selected_checkpoints": {
            name: str(spec["checkpoint"].relative_to(BASE)) for name, spec in MODELS.items()
        },
        "recovered_models": {
            name: str(path.relative_to(BASE)) for name, path in recovered_paths.items()
        },
        "checkpoint_repair": {
            "method": "LayerNorm gamma->weight and beta->bias; strict state-dict load; exact save/reload tensor check",
            "expected_remapped_aliases_per_model": EXPECTED_LAYERNORM_ALIASES,
        },
        "concept_disjoint_model": metrics["concept_disjoint"],
        "full_concept_baseline": metrics["full_concept_baseline"],
        "paired_top1_delta_concept_disjoint_minus_baseline": {
            "estimate": float(delta.mean()),
            "cin_cluster_bootstrap_ci95": delta_ci,
        },
        "previous_unrepaired_result": {
            "concept_disjoint_top1": source_report["concept_disjoint_model"]["top1_accuracy"],
            "full_concept_baseline_top1": source_report["baseline_full_concept_model"]["top1_accuracy"],
        },
        "interpretation": "Weak-label agreement diagnostic only; test rows were already evaluated before technical checkpoint recovery, so this is not a fresh held-out result.",
    }
    REPORT_OUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("\nSTAGE 2 — RECOVERED CHECKPOINT RECHECK (NOT A FRESH TEST)")
    for name, title in (("full_concept_baseline", "Full-concept baseline"), ("concept_disjoint", "Concept-disjoint model")):
        m = metrics[name]
        print(f"{title}: Top1={m['top1_accuracy']:.4f} ({m['top1_correct']}/{m['n']}), Top2={m['top2_accuracy']:.4f}, macro-F1={m['macro_f1']:.4f}")
    print(f"Paired Top1 delta (concept-disjoint - baseline): {delta.mean():+.4f} CIN-bootstrap CI95={delta_ci}")
    print(f"Results: {REPORT_OUT}")


if __name__ == "__main__":
    main()
