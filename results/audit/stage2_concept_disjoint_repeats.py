"""Three-seed concept-disjoint stability analysis for Stage 2.

Seed 42 reuses the already-trained, strictly recovered model and its original
held-out concept set. Seeds 17 and 73 make two additional concept hold-outs
and train one model each. Validation macro-F1 selects each checkpoint; the
held-out test rows are scored once per run. This is a repeated diagnostic on
the same company-disjoint test companies, not three independent test cohorts.

Run from repository root with .venv-ml. The user runs this script; the
assistant does not run it. Expected compute: two additional fine-tuning runs.
"""
from __future__ import annotations

import inspect
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import f1_score
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    DataCollatorWithPadding,
    Trainer,
    TrainingArguments,
)

BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import stage2_concept_disjoint_eval as diag  # noqa: E402

SPLIT_SEEDS = (42, 17, 73)
NUM_LABELS = 9
NUM_EPOCHS = 5
LEARNING_RATE = 2e-5
BATCH_SIZE = 4
GRAD_ACCUM = 4
MAX_LENGTH = 512
BOOTSTRAP_REPS = 2000
BOOTSTRAP_SEED = 420

BASELINE_MODEL = BASE / "data" / "models" / "brsr_company_split_classifier" / "seed_99" / "recovered_checkpoint_7460"
EXISTING_SEED42_MODEL = BASE / "data" / "models" / "brsr_concept_disjoint_classifier" / "seed_42" / "recovered_checkpoint_6270"
EXISTING_SEED42_HOLDOUT = BASE / "data" / "training_concept_disjoint" / "heldout_concepts.json"
ARTIFACT_ROOT = BASE / "data" / "training_concept_disjoint_repeats"
MODEL_ROOT = BASE / "data" / "models" / "brsr_concept_disjoint_repeats"
REPORT_PATH = BASE / "results" / "audit" / "stage2_concept_disjoint_repeats_results.json"


def choose_heldout_concepts(test_c: pd.DataFrame, seed: int) -> list[str]:
    concepts = sorted(test_c["concept"].unique())
    if len(concepts) < 5:
        raise RuntimeError(f"Only {len(concepts)} test concepts; insufficient for holdout.")
    rng = np.random.default_rng(seed)
    concept_labels = test_c.groupby("concept")["label"].agg(lambda values: int(values.mode().iloc[0]))
    heldout = []
    for label in sorted(concept_labels.unique()):
        label_concepts = sorted(concept_labels[concept_labels == label].index.tolist())
        if len(label_concepts) < 2:
            continue
        n_hold = min(len(label_concepts) - 1, max(1, int(round(len(label_concepts) * 0.20))))
        heldout.extend(rng.choice(label_concepts, size=n_hold, replace=False).tolist())
    return sorted(heldout)


def recover_best_checkpoint(model: torch.nn.Module, checkpoint: Path) -> int:
    safe_file = checkpoint / "model.safetensors"
    bin_file = checkpoint / "pytorch_model.bin"
    if safe_file.is_file():
        from safetensors.torch import load_file

        state = load_file(str(safe_file), device="cpu")
    elif bin_file.is_file():
        try:
            state = torch.load(bin_file, map_location="cpu", weights_only=True)
        except TypeError:
            state = torch.load(bin_file, map_location="cpu")
    else:
        raise FileNotFoundError(f"Selected checkpoint has no model weights: {checkpoint}")
    remapped = {}
    aliases = 0
    for key, value in state.items():
        new_key = key
        if "LayerNorm." in key and key.endswith(".gamma"):
            new_key = key[:-len("gamma")] + "weight"
            aliases += 1
        elif "LayerNorm." in key and key.endswith(".beta"):
            new_key = key[:-len("beta")] + "bias"
            aliases += 1
        if new_key in remapped:
            raise RuntimeError(f"Duplicate state key after LayerNorm remap: {new_key}")
        remapped[new_key] = value
    if aliases != 50:
        raise RuntimeError(f"Expected 50 LayerNorm gamma/beta aliases at {checkpoint}; got {aliases}")
    model.load_state_dict(remapped, strict=True)
    return aliases


def train_one(seed: int, train_df: pd.DataFrame, val_df: pd.DataFrame, artifact_dir: Path) -> Path:
    output_root = MODEL_ROOT / f"seed_{seed}"
    if output_root.exists():
        raise FileExistsError(f"Refusing to overwrite existing model directory: {output_root}")
    output_root.mkdir(parents=True, exist_ok=False)

    torch.manual_seed(seed)
    np.random.seed(seed)
    tokenizer = AutoTokenizer.from_pretrained(str(diag.MODEL_SOURCE), local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(
        str(diag.MODEL_SOURCE), num_labels=NUM_LABELS,
        problem_type="single_label_classification", local_files_only=True,
    )

    labels = train_df["label"].to_numpy(dtype=int)
    counts = np.bincount(labels, minlength=NUM_LABELS)
    weights = np.ones(NUM_LABELS, dtype=np.float32)
    present = counts > 0
    weights[present] = len(labels) / (present.sum() * counts[present])
    weights = np.sqrt(weights)
    weights /= weights.mean()
    class_weights = torch.tensor(weights, dtype=torch.float)

    train_ds = diag.BRSRDataset(train_df["text"].fillna("").astype(str).tolist(), labels.tolist(), tokenizer)
    val_labels = val_df["label"].astype(int).tolist()
    val_ds = diag.BRSRDataset(val_df["text"].fillna("").astype(str).tolist(), val_labels, tokenizer)
    kwargs = inspect.signature(TrainingArguments.__init__).parameters
    eval_arg = "eval_strategy" if "eval_strategy" in kwargs else "evaluation_strategy"
    args = TrainingArguments(
        output_dir=str(output_root / "checkpoints"),
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
        fp16=torch.cuda.is_available(),
        report_to="none",
        seed=seed,
        **{eval_arg: "epoch", "save_strategy": "epoch"},
    )
    trainer = diag.WeightedTrainer(
        class_weights=class_weights,
        model=model,
        args=args,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        data_collator=DataCollatorWithPadding(tokenizer=tokenizer),
        compute_metrics=diag.metric_fn,
    )
    trainer.train()
    best = trainer.state.best_model_checkpoint
    if not best:
        raise RuntimeError(f"Training seed {seed} produced no validation-selected checkpoint")
    alias_count = recover_best_checkpoint(trainer.model, Path(best))
    final_dir = output_root / "best_model"
    trainer.save_model(str(final_dir))
    tokenizer.save_pretrained(str(final_dir))
    verified = AutoModelForSequenceClassification.from_pretrained(str(final_dir), local_files_only=True)
    saved_sd = verified.state_dict()
    current_sd = trainer.model.state_dict()
    if saved_sd.keys() != current_sd.keys():
        raise RuntimeError(f"Seed {seed}: saved model parameter keys differ after reload")
    for key in current_sd:
        if not torch.equal(current_sd[key].detach().cpu(), saved_sd[key].detach().cpu()):
            raise RuntimeError(f"Seed {seed}: model tensor changed during save/reload: {key}")
    del verified
    print(f"Seed {seed}: restored validation-best checkpoint strictly ({alias_count} LayerNorm aliases)")
    return final_dir


def main() -> None:
    if REPORT_PATH.exists():
        raise FileExistsError(f"Refusing to overwrite existing report: {REPORT_PATH}")
    if not BASELINE_MODEL.is_dir():
        raise FileNotFoundError(f"Recovered seed-99 baseline missing: {BASELINE_MODEL}")

    print("Reconstructing sample-to-concept links from the local DB...")
    concept_map = diag.reconstruct_final_sample_concepts()
    frames, coverage = diag.load_and_annotate_splits(concept_map)
    test_c = frames["test"][(frames["test"].source == "section_c") & (frames["test"].concept_match_status == "unique")].copy()
    runs = []

    for seed in SPLIT_SEEDS:
        if seed == 42:
            if not EXISTING_SEED42_HOLDOUT.is_file() or not EXISTING_SEED42_MODEL.is_dir():
                raise FileNotFoundError("Seed-42 recovered diagnostic artifacts are missing")
            heldout = json.loads(EXISTING_SEED42_HOLDOUT.read_text(encoding="utf-8"))
            model_dir = EXISTING_SEED42_MODEL
        else:
            heldout = choose_heldout_concepts(test_c, seed)
            model_dir = None
        heldout_set = set(heldout)
        if not heldout_set:
            raise RuntimeError(f"Seed {seed}: empty concept holdout")

        filtered = {}
        for split, df in frames.items():
            unique = df[df["concept_match_status"] == "unique"].copy()
            if split in ("train", "val"):
                unique = unique[~unique["concept"].isin(heldout_set)].copy()
            filtered[split] = unique
        train_df, val_df = filtered["train"], filtered["val"]
        eval_df = filtered["test"][(filtered["test"].source == "section_c") & filtered["test"].concept.isin(heldout_set)].copy()
        if train_df.empty or val_df.empty or eval_df.empty:
            raise RuntimeError(f"Seed {seed}: empty train/validation/evaluation partition")
        if heldout_set & set(train_df["concept"]) or heldout_set & set(val_df["concept"]):
            raise RuntimeError(f"Seed {seed}: held-out concepts leaked into training or validation")
        eval_cins = set(eval_df["cin_norm"])
        if eval_cins & set(train_df["cin_norm"]) or eval_cins & set(val_df["cin_norm"]):
            raise RuntimeError(f"Seed {seed}: company overlap in the held-out evaluation rows")

        if seed == 42:
            prior_eval_path = BASE / "data" / "training_concept_disjoint" / "test_section_c_heldout_concepts.csv"
            prior_eval = pd.read_csv(prior_eval_path, dtype={"cin": "string"})
            key_cols = ["cin_norm", "concept", "text", "label"]
            if not set(key_cols).issubset(prior_eval.columns):
                raise ValueError("Original seed-42 evaluation artifact lacks row-identity columns")
            left = eval_df[key_cols].reset_index(drop=True)
            right = prior_eval[key_cols].reset_index(drop=True)
            if not left.equals(right):
                raise RuntimeError("Seed-42 reconstructed holdout differs from the originally evaluated rows")

        artifact_dir = ARTIFACT_ROOT / f"seed_{seed}"
        if artifact_dir.exists():
            raise FileExistsError(f"Refusing to overwrite existing split artifacts: {artifact_dir}")
        artifact_dir.mkdir(parents=True, exist_ok=False)
        train_df.to_csv(artifact_dir / "train.csv", index=False)
        val_df.to_csv(artifact_dir / "val.csv", index=False)
        eval_df.to_csv(artifact_dir / "test_section_c_heldout_concepts.csv", index=False)
        (artifact_dir / "heldout_concepts.json").write_text(json.dumps(heldout, indent=2), encoding="utf-8")

        if model_dir is None:
            print(f"\nTraining seed {seed}: {len(train_df)} train; {len(val_df)} val; {len(eval_df)} held-out test rows")
            model_dir = train_one(seed, train_df, val_df, artifact_dir)
        else:
            print(f"\nSeed 42: reusing recovered model; {len(eval_df)} held-out test rows")

        baseline_pred, baseline_top2 = diag.infer(BASELINE_MODEL, eval_df)
        model_pred, model_top2 = diag.infer(model_dir, eval_df)
        current = diag.summarize(eval_df, model_pred, model_top2)
        baseline = diag.summarize(eval_df, baseline_pred, baseline_top2)
        delta_hit = (model_pred == eval_df["label"].to_numpy()).astype(float) - (baseline_pred == eval_df["label"].to_numpy()).astype(float)
        delta_ci = diag.bootstrap_ci(delta_hit + 1.0, eval_df["cin_norm"].to_numpy())
        if delta_ci is not None:
            delta_ci = [delta_ci[0] - 1.0, delta_ci[1] - 1.0]
        runs.append({
            "holdout_seed": seed,
            "n_heldout_concepts": len(heldout),
            "heldout_concepts": heldout,
            "n_train": len(train_df),
            "n_validation": len(val_df),
            "n_test": len(eval_df),
            "n_test_cins": int(eval_df["cin_norm"].nunique()),
            "model": str(model_dir.relative_to(BASE)),
            "baseline_recovered": baseline,
            "concept_disjoint_recovered": current,
            "paired_top1_delta_model_minus_baseline": {
                "estimate": float(delta_hit.mean()),
                "cin_cluster_bootstrap_ci95": delta_ci,
            },
        })
        print(f"Seed {seed}: Top-1={current['top1_accuracy']:.4f}; Top-2={current['top2_accuracy']:.4f}; macro-F1={current['macro_f1']:.4f}")

    def mean_sd(metric: str, model_key: str = "concept_disjoint_recovered") -> dict:
        vals = np.asarray([run[model_key][metric] for run in runs], dtype=float)
        return {"mean": float(vals.mean()), "sample_sd": float(vals.std(ddof=1)), "per_holdout": vals.tolist()}

    summary = {
        "evaluation": "Three concept-disjoint hold-out stability runs on Stage 3 company-disjoint test companies",
        "fresh_test": False,
        "holdout_seeds": list(SPLIT_SEEDS),
        "holdout_design": "20% of test-present Section C concepts, stratified by weak-label principle where multiple concepts exist; selected concepts purged from all unique train/validation rows",
        "run_42_reused": True,
        "additional_training_runs": 2,
        "concept_link_coverage": coverage,
        "metrics_mean_sd_across_holdouts": {
            "concept_disjoint_top1_accuracy": mean_sd("top1_accuracy"),
            "concept_disjoint_top2_accuracy": mean_sd("top2_accuracy"),
            "concept_disjoint_macro_f1": mean_sd("macro_f1"),
            "full_concept_baseline_top1_accuracy": mean_sd("top1_accuracy", "baseline_recovered"),
            "paired_top1_delta_model_minus_baseline": mean_sd("estimate", "paired_top1_delta_model_minus_baseline"),
        },
        "runs": runs,
        "limitations": [
            "All hold-outs reuse companies and rows from the same established company-disjoint test partition; they are not independent test cohorts.",
            "Seed 42 uses an already-observed hold-out and recovered checkpoint; this is a stability diagnostic, not fresh independent confirmation.",
            "One training seed per concept hold-out; between-run standard deviation mixes concept-split and training-seed variation.",
            "Labels remain taxonomy-derived weak labels, so scores measure agreement and do not establish human-ground-truth semantic understanding.",
            "P7/P9 may have sparse or absent held-out-concept examples; report support and avoid unqualified macro-F1 interpretation.",
        ],
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("\nSTAGE 2 — CONCEPT-DISJOINT STABILITY (THREE HOLD-OUTS)")
    for key, values in summary["metrics_mean_sd_across_holdouts"].items():
        print(f"{key}: mean={values['mean']:.4f}; sample SD={values['sample_sd']:.4f}; runs={values['per_holdout']}")
    print(f"Results: {REPORT_PATH}")


if __name__ == "__main__":
    main()
