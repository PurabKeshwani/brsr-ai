"""Re-evaluate the recovered Stage 3 seed-99 checkpoint on the full test set.

Also recomputes the zero-shot Stage 5 comparator on the identical rows so the
Stage 5 paired comparison corresponds to the recovered supervised model.
This is a re-evaluation of an already-used test set, not a fresh test.

Run from repository root with .venv-ml. The user runs this script; the
assistant does not run it.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import classification_report, confusion_matrix, f1_score

import stage5_company_disjoint_eval as stage5

BASE = Path(__file__).resolve().parents[2]
TEST_PATH = BASE / "data" / "training_company_split" / "test.csv"
RECOVERED_MODEL = BASE / "data" / "models" / "brsr_company_split_classifier" / "seed_99" / "recovered_checkpoint_7460"
STAGE3_OUT = BASE / "results" / "audit" / "stage3_seed99_recovered_full_results.json"
STAGE5_OUT = BASE / "results" / "audit" / "stage5_company_disjoint_recovered_results.json"
BOOTSTRAP_REPS = 2000
BOOTSTRAP_SEED = 4206


def cluster_indices(groups: np.ndarray) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    names = np.unique(groups)
    return names, {name: np.flatnonzero(groups == name) for name in names}


def bootstrap_metric_cis(y: np.ndarray, pred: np.ndarray, top2: np.ndarray, groups: np.ndarray) -> dict:
    names, rows_by_name = cluster_indices(groups)
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    samples = {"top1": [], "top2": [], "macro_f1": []}
    for _ in range(BOOTSTRAP_REPS):
        chosen = rng.choice(names, size=len(names), replace=True)
        idx = np.concatenate([rows_by_name[name] for name in chosen])
        hit1 = pred[idx] == y[idx]
        hit2 = np.any(top2[idx] == y[idx, None], axis=1)
        samples["top1"].append(float(hit1.mean()))
        samples["top2"].append(float(hit2.mean()))
        samples["macro_f1"].append(float(f1_score(y[idx], pred[idx], labels=list(range(9)), average="macro", zero_division=0)))
    return {key: [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))] for key, vals in samples.items()}


def paired_bootstrap_cis(
    y: np.ndarray, zero1: np.ndarray, zero2: np.ndarray, sup1: np.ndarray, sup2: np.ndarray, groups: np.ndarray
) -> dict:
    names, rows_by_name = cluster_indices(groups)
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    samples = {"top1_delta": [], "top2_delta": []}
    for _ in range(BOOTSTRAP_REPS):
        chosen = rng.choice(names, size=len(names), replace=True)
        idx = np.concatenate([rows_by_name[name] for name in chosen])
        z1 = zero1[idx] == y[idx]
        z2 = np.any(zero2[idx] == y[idx, None], axis=1)
        s1 = sup1[idx] == y[idx]
        s2 = np.any(sup2[idx] == y[idx, None], axis=1)
        samples["top1_delta"].append(float(s1.mean() - z1.mean()))
        samples["top2_delta"].append(float(s2.mean() - z2.mean()))
    return {key: [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))] for key, vals in samples.items()}


def source_metrics(test: pd.DataFrame, y: np.ndarray, pred: np.ndarray, top2: np.ndarray) -> dict:
    output = {}
    for source in ("section_b", "section_c", "notes_principle"):
        mask = test["source"].eq(source).to_numpy()
        part = test.loc[mask]
        part_hit = pred[mask] == y[mask]
        top2_hit = np.any(top2[mask] == y[mask, None], axis=1)
        if mask.any():
            source_cis = bootstrap_metric_cis(
                y[mask], pred[mask], top2[mask], part["cin_norm"].to_numpy()
            )
            output[source] = {
                "n": int(mask.sum()),
                "unique_cins": int(part["cin_norm"].nunique()),
                "top1_correct": int(part_hit.sum()),
                "top1_accuracy": float(part_hit.mean()),
                "top1_cin_cluster_bootstrap_ci95": source_cis["top1"],
                "top2_correct": int(top2_hit.sum()),
                "top2_accuracy": float(top2_hit.mean()),
                "macro_f1_top1": float(f1_score(y[mask], pred[mask], labels=list(range(9)), average="macro", zero_division=0)),
                "per_principle": {},
            }
            for label in range(9):
                class_mask = mask & (y == label)
                output[source]["per_principle"][f"P{label + 1}"] = {
                    "n": int(class_mask.sum()),
                    "top1_accuracy": float((pred[class_mask] == y[class_mask]).mean()) if class_mask.any() else None,
                    "top2_accuracy": float(np.any(top2[class_mask] == y[class_mask, None], axis=1).mean()) if class_mask.any() else None,
                }
        else:
            output[source] = {"n": 0, "unique_cins": 0, "top1_accuracy": None, "top2_accuracy": None}
    return output


def classifier_metrics(y: np.ndarray, pred: np.ndarray, top2: np.ndarray, groups: np.ndarray) -> dict:
    top1_hit = pred == y
    top2_hit = np.any(top2 == y[:, None], axis=1)
    cis = bootstrap_metric_cis(y, pred, top2, groups)
    return {
        "top1_correct": int(top1_hit.sum()),
        "top1_accuracy": float(top1_hit.mean()),
        "top1_cin_cluster_bootstrap_ci95": cis["top1"],
        "top2_correct": int(top2_hit.sum()),
        "top2_accuracy": float(top2_hit.mean()),
        "top2_cin_cluster_bootstrap_ci95": cis["top2"],
        "macro_f1_top1": float(f1_score(y, pred, labels=list(range(9)), average="macro", zero_division=0)),
        "macro_f1_cin_cluster_bootstrap_ci95": cis["macro_f1"],
        "confusion_matrix": confusion_matrix(y, pred, labels=list(range(9))).tolist(),
        "classification_report": classification_report(y, pred, labels=list(range(9)), output_dict=True, zero_division=0),
        "per_principle": {
            f"P{label + 1}": {
                "n": int((y == label).sum()),
                "top1_correct": int(((y == label) & (pred == y)).sum()),
                "top1_accuracy": float((pred[y == label] == y[y == label]).mean()) if np.any(y == label) else None,
                "top2_accuracy": float(np.any(top2[y == label] == y[y == label, None], axis=1).mean()) if np.any(y == label) else None,
            }
            for label in range(9)
        },
    }


def main() -> None:
    if not RECOVERED_MODEL.is_dir():
        raise FileNotFoundError(
            f"Recovered seed-99 model not found: {RECOVERED_MODEL}. Run stage2_recover_layernorm_and_eval.py first."
        )
    if not TEST_PATH.is_file():
        raise FileNotFoundError(f"Company-disjoint test CSV missing: {TEST_PATH}")

    # Reuse Stage 5's split assertions and inference implementation, but point
    # it at the strictly recovered selected checkpoint.
    stage5.SUPERVISED_MODEL_PATH = RECOVERED_MODEL
    test, test_cins = stage5.assert_company_disjoint()
    if len(test) != 6201 or len(test_cins) != 175:
        raise ValueError(f"Expected the audited N=6201 / 175-CIN test; found {len(test)} / {len(test_cins)}")
    y = test["label"].to_numpy(dtype=int)
    groups = test["cin_norm"].to_numpy()
    texts = test["text"].fillna("").astype(str).tolist()
    print(f"Recovered seed-99 full test: N={len(test)}; CINs={len(test_cins)}; company-disjoint assertions PASS")
    print("Computing recovered supervised classifier predictions...")
    sup1, sup2 = stage5.supervised_topk_predictions(texts)
    print("Computing zero-shot MPNet hybrid on the same rows for the Stage 5 comparison...")
    zero1, zero2 = stage5.topk_predictions(texts)

    recovered_metrics = classifier_metrics(y, sup1, sup2, groups)
    sources = source_metrics(test, y, sup1, sup2)
    recovered_stage3 = {
        "evaluation": "Stage 3 seed-99 recovered checkpoint re-evaluation on the full company-disjoint test",
        "fresh_test": False,
        "test_dataset": str(TEST_PATH.relative_to(BASE)),
        "test_sha256": hashlib.sha256(TEST_PATH.read_bytes()).hexdigest(),
        "n_segments": int(len(test)),
        "n_company_clusters_cin": int(len(test_cins)),
        "company_disjoint_assertions": True,
        "selected_checkpoint": "data/models/brsr_company_split_classifier/seed_99/checkpoints/checkpoint-7460",
        "recovered_model": str(RECOVERED_MODEL.relative_to(BASE)),
        "checkpoint_recovery": "50 LayerNorm gamma/beta aliases strictly remapped; save/reload tensors verified exactly in the Stage 2 recovery step",
        "metrics": recovered_metrics,
        "source_metrics": sources,
        "interpretation": "Re-evaluation of a previously used test set; labels are taxonomy-derived weak labels, not independent human ground truth.",
    }

    zero_metrics = classifier_metrics(y, zero1, zero2, groups)
    paired_ci = paired_bootstrap_cis(y, zero1, zero2, sup1, sup2, groups)
    stage5_result = {
        "evaluation": "Stage 5 supervised transfer vs zero-shot MPNet hybrid, with recovered Stage 3 seed-99 model",
        "fresh_test": False,
        "test_dataset": str(TEST_PATH.relative_to(BASE)),
        "test_sha256": recovered_stage3["test_sha256"],
        "n_segments": int(len(test)),
        "n_company_clusters_cin": int(len(test_cins)),
        "stage3_company_disjoint_assertions": True,
        "supervised_model": str(RECOVERED_MODEL.relative_to(BASE)),
        "supervised_model_selection": "seed 99, selected on Stage 3 validation macro-F1; selected checkpoint-7460 recovered with strict LayerNorm key remapping",
        "comparison_framing": "supervised transfer vs zero-shot embedding on identical company-disjoint test segments; not an isolated alignment-scoring gain",
        "bootstrap": {"method": "CIN cluster bootstrap, paired between methods", "replicates": BOOTSTRAP_REPS, "seed": BOOTSTRAP_SEED, "ci_level": 0.95},
        "metrics": {
            "zero_shot": zero_metrics,
            "supervised_transfer": recovered_metrics,
            "paired_delta_supervised_minus_zero_shot": {
                "top1": float((sup1 == y).mean() - (zero1 == y).mean()),
                "top1_ci95": paired_ci["top1_delta"],
                "top2": float(np.any(sup2 == y[:, None], axis=1).mean() - np.any(zero2 == y[:, None], axis=1).mean()),
                "top2_ci95": paired_ci["top2_delta"],
            },
        },
        "per_principle_top1": {
            f"P{label + 1}": {
                "support": int((y == label).sum()),
                "zero_shot_top1_accuracy": float((zero1[y == label] == y[y == label]).mean()) if np.any(y == label) else None,
                "supervised_top1_accuracy": float((sup1[y == label] == y[y == label]).mean()) if np.any(y == label) else None,
            }
            for label in range(9)
        },
        "limitations": [
            "This reuses the previously evaluated company-disjoint test set; it is a checkpoint-correctness re-evaluation, not a fresh test.",
            "Stage 3 labels are taxonomy-derived weak labels, including AI-assisted mappings, not independent human ground truth.",
            "The comparison is supervised transfer vs zero-shot embedding, not an isolated causal effect of domain adaptation or alignment scoring.",
            "Top-k principle classification does not by itself establish regulatory compliance.",
        ],
    }

    STAGE3_OUT.write_text(json.dumps(recovered_stage3, indent=2), encoding="utf-8")
    STAGE5_OUT.write_text(json.dumps(stage5_result, indent=2), encoding="utf-8")
    print("\nSTAGE 3 — RECOVERED SEED-99 FULL TEST")
    print(f"Top-1={recovered_metrics['top1_accuracy']:.4f} ({recovered_metrics['top1_correct']}/{len(test)}) CI95={recovered_metrics['top1_cin_cluster_bootstrap_ci95']}")
    print(f"Top-2={recovered_metrics['top2_accuracy']:.4f} ({recovered_metrics['top2_correct']}/{len(test)}) CI95={recovered_metrics['top2_cin_cluster_bootstrap_ci95']}")
    print(f"Macro-F1={recovered_metrics['macro_f1_top1']:.4f} CI95={recovered_metrics['macro_f1_cin_cluster_bootstrap_ci95']}")
    print("Source Top-1: " + "; ".join(f"{name}={m['top1_accuracy']:.4f} (n={m['n']})" for name, m in sources.items()))
    d = stage5_result["metrics"]["paired_delta_supervised_minus_zero_shot"]
    print(f"Stage 5 paired Top-1 delta={d['top1']:+.4f} CI95={d['top1_ci95']}")
    print(f"Stage 3 results: {STAGE3_OUT}")
    print(f"Stage 5 results: {STAGE5_OUT}")
    print("Status: prior test set re-evaluated; not a fresh test")


if __name__ == "__main__":
    main()
