"""Build and evaluate a company-disjoint multi-label Stage 2 classifier.

Each company + normalized narrative becomes one row with the union of all
observed taxonomy/source labels. Unlike the single-label builder, this keeps
multi-principle groups instead of discarding them as contradictions. The
existing company CIN assignments are reused for strict train/val/test
separation. The recovered single-label seed-99 classifier is scored on the
same multi-label test rows as a reference baseline.

Primary metrics use a fixed 0.5 sigmoid threshold: micro/macro F1 and exact
set accuracy, plus ranking Hit@1/Hit@2. No threshold tuning on the test set.
The user runs this script with .venv-ml; the assistant does not run it.
"""
from __future__ import annotations

import inspect
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.metrics import f1_score, precision_score, recall_score
from torch.utils.data import Dataset
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    DataCollatorWithPadding,
    Trainer,
    TrainingArguments,
)

BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE / "src"))
sys.path.insert(0, str(BASE / "scripts" / "03_bert_training"))

import build_training_dataset as builder  # noqa: E402
from db.models import Company, Fact, Filing  # noqa: E402
from db.session import get_session  # noqa: E402

NUM_LABELS = 9
SEED = 42
MAX_LENGTH = 512
EPOCHS = 5
LEARNING_RATE = 2e-5
BATCH_SIZE = 4
GRAD_ACCUM = 4
BOOTSTRAP_REPS = 1000
BOOTSTRAP_SEED = 6042

SPLIT_DIR = BASE / "data" / "training_company_split"
BASE_ENCODER = BASE / "data" / "models" / "domain_adapted_bert" / "final_model"
SINGLE_LABEL_BASELINE = BASE / "data" / "models" / "brsr_company_split_classifier" / "seed_99" / "recovered_checkpoint_7460"
DATA_DIR = BASE / "data" / "training_multilabel_company_split"
MODEL_DIR = BASE / "data" / "models" / "brsr_multilabel_classifier" / f"seed_{SEED}"
REPORT_PATH = BASE / "results" / "audit" / "stage2_multilabel_results.json"
SOURCES = ("section_b", "section_c", "notes_principle")
LABEL_COLUMNS = [f"y{i}" for i in range(NUM_LABELS)]


def normalize_cin(value: object) -> str:
    return str(value or "").strip().upper()


def split_company_map() -> dict[str, str]:
    assignment: dict[str, str] = {}
    for split in ("train", "val", "test"):
        path = SPLIT_DIR / f"{split}.csv"
        frame = pd.read_csv(path, dtype={"cin": "string"})
        if "cin" not in frame:
            raise ValueError(f"{path} has no cin column")
        for cin in frame["cin"].dropna().map(normalize_cin).unique():
            if not cin:
                raise ValueError(f"Blank CIN in {path}")
            previous = assignment.get(cin)
            if previous and previous != split:
                raise RuntimeError(f"CIN {cin} is assigned to both {previous} and {split}")
            assignment[cin] = split
    return assignment


def collect_multilabel_groups(company_split: dict[str, str]) -> tuple[list[dict], dict]:
    """Collect all recognized labels and union them by company + clean text."""
    grouped: dict[tuple[int, str], dict] = {}
    stats = Counter()
    unmapped_companies = set()
    with get_session() as session:
        companies = session.query(Company).all()
        for company in companies:
            cin = normalize_cin(company.cin)
            if not cin:
                continue
            filings = session.query(Filing).filter_by(company_id=company.id).all()
            for filing in filings:
                facts = session.query(Fact).filter(
                    Fact.filing_id == filing.id,
                    Fact.concept.like("%ExplanatoryTextBlock%"),
                ).all()
                for fact in facts:
                    if not fact.value:
                        continue
                    raw = fact.value.strip()
                    if not builder.is_clean_narrative(raw):
                        stats["noise_filtered_facts"] += 1
                        continue
                    text = builder.URL_PATTERN.sub("", raw).strip()
                    text = re.sub(r"\s+", " ", text).strip()
                    candidates: list[tuple[str, int]] = []
                    axis = (fact.dimensions or {}).get("PrincipleAxis")
                    if axis in builder.PRINCIPLE_TO_LABEL:
                        candidates.append(("section_b", builder.PRINCIPLE_TO_LABEL[axis]))
                    if fact.concept in builder.SECTION_C_CONCEPT_TO_LABEL:
                        candidates.append(("section_c", builder.SECTION_C_CONCEPT_TO_LABEL[fact.concept]))
                    if fact.concept in builder.NOTES_PRINCIPLE_CONCEPTS:
                        candidates.append(("notes_principle", builder.NOTES_PRINCIPLE_CONCEPTS[fact.concept]))
                    if not candidates:
                        stats["clean_but_unlabeled_facts"] += 1
                        continue
                    stats["labeled_fact_candidates"] += 1
                    key = (company.id, text)
                    row = grouped.setdefault(key, {
                        "text": text,
                        "cin": cin,
                        "company_name": str(company.name or ""),
                        "labels": set(),
                        "sources": set(),
                        "concepts": set(),
                    })
                    for source, label in candidates:
                        row["labels"].add(int(label))
                        row["sources"].add(source)
                        row["concepts"].add(str(fact.concept))
                        stats[f"candidate_labels_{source}"] += 1

    rows = []
    for row in grouped.values():
        labels = sorted(row["labels"])
        if not labels:
            continue
        cin = row["cin"]
        split = company_split.get(cin, "train")  # unseen firms are train-only, never added to val/test
        if cin not in company_split:
            unmapped_companies.add(cin)
        record = {
            "text": row["text"],
            "label_list": json.dumps(labels),
            "label_count": len(labels),
            "source_types": "+".join(sorted(row["sources"])),
            "concept_count": len(row["concepts"]),
            "company_name": row["company_name"],
            "cin": cin,
            "split": split,
        }
        for idx in range(NUM_LABELS):
            record[f"y{idx}"] = int(idx in row["labels"])
        rows.append(record)
    stats["unique_company_text_groups"] = len(rows)
    stats["multilabel_groups"] = sum(row["label_count"] > 1 for row in rows)
    stats["unseen_company_cins_assigned_train_only"] = len(unmapped_companies)
    stats["label_cardinality_distribution"] = dict(Counter(str(row["label_count"]) for row in rows))
    return rows, dict(stats)


class MultiLabelDataset(Dataset):
    def __init__(self, frame: pd.DataFrame, tokenizer):
        self.texts = frame["text"].fillna("").astype(str).tolist()
        self.targets = frame[LABEL_COLUMNS].to_numpy(dtype=np.float32)
        self.tokenizer = tokenizer

    def __len__(self) -> int:
        return len(self.texts)

    def __getitem__(self, index: int) -> dict:
        encoded = self.tokenizer(self.texts[index], truncation=True, max_length=MAX_LENGTH)
        encoded["labels"] = self.targets[index].tolist()
        return encoded


class MultiLabelTrainer(Trainer):
    def __init__(self, pos_weight: torch.Tensor, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pos_weight = pos_weight

    def compute_loss(self, model, inputs, return_outputs=False, num_items_in_batch=None):
        labels = inputs.pop("labels").float()
        outputs = model(**inputs)
        loss_fn = nn.BCEWithLogitsLoss(pos_weight=self.pos_weight.to(outputs.logits.device))
        loss = loss_fn(outputs.logits, labels)
        return (loss, outputs) if return_outputs else loss


def sigmoid(logits: np.ndarray) -> np.ndarray:
    logits = np.clip(logits, -40, 40)
    return 1.0 / (1.0 + np.exp(-logits))


def multilabel_metric_dict(y: np.ndarray, probs: np.ndarray, binary_predictions: np.ndarray | None = None) -> dict:
    y = y.astype(int)
    threshold_pred = (probs >= 0.5).astype(int) if binary_predictions is None else binary_predictions.astype(int)
    ranking = np.argsort(-probs, axis=1)
    hit1 = y[np.arange(len(y)), ranking[:, 0]].astype(bool)
    hit2 = np.any(np.take_along_axis(y, ranking[:, :2], axis=1) == 1, axis=1)
    supports = y.sum(axis=0)
    return {
        "n": int(len(y)),
        "gold_label_assignments": int(y.sum()),
        "mean_gold_labels_per_text": float(y.sum(axis=1).mean()),
        "mean_predicted_labels_per_text_at_0_5": float(threshold_pred.sum(axis=1).mean()),
        "hit_at_1": float(hit1.mean()),
        "hit_at_1_correct_rows": int(hit1.sum()),
        "hit_at_2": float(hit2.mean()),
        "hit_at_2_correct_rows": int(hit2.sum()),
        "micro_precision_at_0_5": float(precision_score(y, threshold_pred, average="micro", zero_division=0)),
        "micro_recall_at_0_5": float(recall_score(y, threshold_pred, average="micro", zero_division=0)),
        "micro_f1_at_0_5": float(f1_score(y, threshold_pred, average="micro", zero_division=0)),
        "macro_f1_at_0_5": float(f1_score(y, threshold_pred, average="macro", zero_division=0)),
        "exact_set_match_at_0_5": float(np.all(y == threshold_pred, axis=1).mean()),
        "per_principle": {
            f"P{i + 1}": {
                "support_positive_rows": int(supports[i]),
                "precision": float(precision_score(y[:, i], threshold_pred[:, i], zero_division=0)),
                "recall": float(recall_score(y[:, i], threshold_pred[:, i], zero_division=0)),
                "f1": float(f1_score(y[:, i], threshold_pred[:, i], zero_division=0)),
            }
            for i in range(NUM_LABELS)
        },
    }


def bootstrap_cis(
    y: np.ndarray, probs: np.ndarray, groups: np.ndarray, binary_predictions: np.ndarray | None = None
) -> dict:
    names = np.unique(groups)
    rows = {name: np.flatnonzero(groups == name) for name in names}
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    values = {key: [] for key in ("hit_at_1", "hit_at_2", "micro_f1_at_0_5", "macro_f1_at_0_5")}
    for _ in range(BOOTSTRAP_REPS):
        chosen = rng.choice(names, size=len(names), replace=True)
        idx = np.concatenate([rows[name] for name in chosen])
        sampled_binary = binary_predictions[idx] if binary_predictions is not None else None
        metrics = multilabel_metric_dict(y[idx], probs[idx], sampled_binary)
        for key in values:
            values[key].append(metrics[key])
    return {key: [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))] for key, v in values.items()}


def predict_probabilities(model_dir: Path, frame: pd.DataFrame, multilabel: bool) -> np.ndarray:
    tokenizer = AutoTokenizer.from_pretrained(str(model_dir), local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(str(model_dir), local_files_only=True)
    model.eval()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    logits_all = []
    texts = frame["text"].fillna("").astype(str).tolist()
    with torch.no_grad():
        for start in range(0, len(texts), 8):
            batch = tokenizer(texts[start:start + 8], padding=True, truncation=True, max_length=MAX_LENGTH, return_tensors="pt").to(device)
            logits_all.append(model(**batch).logits.float().cpu().numpy())
    del model
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    logits = np.vstack(logits_all)
    if logits.shape != (len(frame), NUM_LABELS):
        raise ValueError(f"Expected logits shape {(len(frame), NUM_LABELS)}, got {logits.shape}")
    if multilabel:
        return sigmoid(logits)
    return torch.softmax(torch.from_numpy(logits), dim=1).numpy()


def compute_metrics(eval_pred):
    logits, labels = eval_pred
    metrics = multilabel_metric_dict(labels, sigmoid(logits))
    return {key: metrics[key] for key in ("hit_at_1", "hit_at_2", "micro_f1_at_0_5", "macro_f1_at_0_5", "exact_set_match_at_0_5")}


def recover_selected_checkpoint(model: torch.nn.Module, checkpoint: Path) -> int:
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
        raise FileNotFoundError(f"No model weights at selected checkpoint {checkpoint}")
    mapped = {}
    aliases = 0
    for key, value in state.items():
        new = key
        if "LayerNorm." in key and key.endswith(".gamma"):
            new = key[:-5] + "weight"
            aliases += 1
        elif "LayerNorm." in key and key.endswith(".beta"):
            new = key[:-4] + "bias"
            aliases += 1
        if new in mapped:
            raise RuntimeError(f"Duplicate key after LayerNorm remapping: {new}")
        mapped[new] = value
    if aliases != 50:
        raise RuntimeError(f"Expected 50 LayerNorm aliases, got {aliases}; refusing unsafe restore")
    model.load_state_dict(mapped, strict=True)
    return aliases


def main() -> None:
    for path in (DATA_DIR, MODEL_DIR, REPORT_PATH):
        if path.exists():
            raise FileExistsError(f"Refusing to overwrite existing artifact: {path}")
    if not BASE_ENCODER.is_dir() or not SINGLE_LABEL_BASELINE.is_dir():
        raise FileNotFoundError("Local base encoder or recovered single-label baseline is missing")

    assignment = split_company_map()
    rows, collection_stats = collect_multilabel_groups(assignment)
    full = pd.DataFrame(rows)
    if full.empty:
        raise RuntimeError("No multi-label text groups collected")
    splits = {name: full[full["split"] == name].reset_index(drop=True) for name in ("train", "val", "test")}
    if any(splits[name].empty for name in splits):
        raise RuntimeError("One or more company-disjoint multi-label splits are empty")
    cin_sets = {name: set(splits[name]["cin"]) for name in splits}
    for a, b in (("train", "val"), ("train", "test"), ("val", "test")):
        overlap = cin_sets[a] & cin_sets[b]
        if overlap:
            raise RuntimeError(f"Company leakage in multi-label split {a}/{b}: {len(overlap)} CINs")

    DATA_DIR.mkdir(parents=True, exist_ok=False)
    for name, frame in splits.items():
        frame.to_csv(DATA_DIR / f"{name}.csv", index=False)
    class_support = {f"P{i + 1}": int(splits["train"][f"y{i}"].sum()) for i in range(NUM_LABELS)}
    train_y = splits["train"][LABEL_COLUMNS].to_numpy(dtype=np.float32)
    positives = train_y.sum(axis=0)
    negatives = len(train_y) - positives
    pos_weight = np.ones(NUM_LABELS, dtype=np.float32)
    present = positives > 0
    pos_weight[present] = np.minimum(8.0, np.sqrt(negatives[present] / positives[present]))

    torch.manual_seed(SEED)
    np.random.seed(SEED)
    tokenizer = AutoTokenizer.from_pretrained(str(BASE_ENCODER), local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(
        str(BASE_ENCODER), num_labels=NUM_LABELS, problem_type="multi_label_classification",
        id2label={i: f"Principle{i + 1}Member" for i in range(NUM_LABELS)},
        label2id={f"Principle{i + 1}Member": i for i in range(NUM_LABELS)},
        local_files_only=True,
    )
    train_ds = MultiLabelDataset(splits["train"], tokenizer)
    val_ds = MultiLabelDataset(splits["val"], tokenizer)
    kwargs = inspect.signature(TrainingArguments.__init__).parameters
    eval_arg = "eval_strategy" if "eval_strategy" in kwargs else "evaluation_strategy"
    args = TrainingArguments(
        output_dir=str(MODEL_DIR / "checkpoints"),
        num_train_epochs=EPOCHS,
        per_device_train_batch_size=BATCH_SIZE,
        per_device_eval_batch_size=BATCH_SIZE * 2,
        gradient_accumulation_steps=GRAD_ACCUM,
        learning_rate=LEARNING_RATE,
        weight_decay=0.01,
        warmup_steps=300,
        lr_scheduler_type="cosine",
        load_best_model_at_end=True,
        metric_for_best_model="macro_f1_at_0_5",
        greater_is_better=True,
        save_total_limit=2,
        logging_steps=100,
        fp16=torch.cuda.is_available(),
        report_to="none",
        seed=SEED,
        **{eval_arg: "epoch", "save_strategy": "epoch"},
    )
    trainer = MultiLabelTrainer(
        pos_weight=torch.tensor(pos_weight, dtype=torch.float),
        model=model,
        args=args,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        data_collator=DataCollatorWithPadding(tokenizer=tokenizer),
        compute_metrics=compute_metrics,
    )
    print(f"Multi-label rows: train={len(splits['train'])}, val={len(splits['val'])}, test={len(splits['test'])}")
    print(f"Companies: train={len(cin_sets['train'])}, val={len(cin_sets['val'])}, test={len(cin_sets['test'])}; overlap=0")
    print(f"Rows with multiple labels: {int((full['label_count'] > 1).sum())}; train positive support={class_support}")
    print("Training multi-label BCE model; validation macro-F1 selects checkpoint; fixed 0.5 threshold, no test tuning...")
    trainer.train()
    best_path = trainer.state.best_model_checkpoint
    if not best_path:
        raise RuntimeError("No validation-selected best checkpoint was produced")
    alias_count = recover_selected_checkpoint(trainer.model, Path(best_path))
    final_model = MODEL_DIR / "best_model"
    trainer.save_model(str(final_model))
    tokenizer.save_pretrained(str(final_model))
    verified = AutoModelForSequenceClassification.from_pretrained(str(final_model), local_files_only=True)
    current_sd, saved_sd = trainer.model.state_dict(), verified.state_dict()
    if current_sd.keys() != saved_sd.keys() or any(not torch.equal(current_sd[k].detach().cpu(), saved_sd[k].detach().cpu()) for k in current_sd):
        raise RuntimeError("Saved multi-label checkpoint failed exact tensor reload verification")
    del verified
    print(f"Selected checkpoint restored strictly; remapped {alias_count} LayerNorm aliases; save/reload PASS")

    test = splits["test"].reset_index(drop=True)
    y_test = test[LABEL_COLUMNS].to_numpy(dtype=int)
    multi_probs = predict_probabilities(final_model, test, multilabel=True)
    baseline_probs = predict_probabilities(SINGLE_LABEL_BASELINE, test, multilabel=False)
    multi_metrics = multilabel_metric_dict(y_test, multi_probs)
    baseline_top1 = np.argmax(baseline_probs, axis=1)
    baseline_binary = np.zeros_like(y_test)
    baseline_binary[np.arange(len(y_test)), baseline_top1] = 1
    baseline_metrics = multilabel_metric_dict(y_test, baseline_probs, baseline_binary)
    multi_metrics["cin_cluster_bootstrap_ci95"] = bootstrap_cis(y_test, multi_probs, test["cin"].to_numpy())
    baseline_metrics["decision_rule"] = "single-label argmax converted to one predicted label per text"
    baseline_metrics["cin_cluster_bootstrap_ci95"] = bootstrap_cis(
        y_test, baseline_probs, test["cin"].to_numpy(), baseline_binary
    )

    source_metrics = {}
    for source in SOURCES:
        mask = test["source_types"].astype(str).str.split("+").map(lambda vals: source in vals).to_numpy()
        if not mask.any():
            continue
        subset_y = y_test[mask]
        subset_probs = multi_probs[mask]
        source_metrics[source] = {
            "n_rows": int(mask.sum()),
            "cin_count": int(test.loc[mask, "cin"].nunique()),
            **multilabel_metric_dict(subset_y, subset_probs),
        }

    report = {
        "evaluation": "Exploratory multi-label Stage 2 classifier on the existing company-disjoint partition",
        "fresh_test": False,
        "task": "company + cleaned narrative -> set of all observed taxonomy/source principle labels",
        "split": {
            "dataset_dir": str(DATA_DIR.relative_to(BASE)),
            "train_rows": int(len(splits["train"])),
            "val_rows": int(len(splits["val"])),
            "test_rows": int(len(splits["test"])),
            "train_cins": len(cin_sets["train"]),
            "val_cins": len(cin_sets["val"]),
            "test_cins": len(cin_sets["test"]),
            "pairwise_cin_overlap": 0,
        },
        "collection": collection_stats,
        "training_label_support": class_support,
        "training": {
            "encoder": str(BASE_ENCODER.relative_to(BASE)),
            "loss": "BCEWithLogitsLoss with capped sqrt(negative/positive) pos_weight",
            "validation_selection": "macro-F1 at fixed sigmoid threshold 0.5",
            "test_threshold_tuning": False,
            "epochs": EPOCHS,
            "learning_rate": LEARNING_RATE,
            "seed": SEED,
            "selected_checkpoint": str(Path(best_path).relative_to(BASE)),
            "final_model": str(final_model.relative_to(BASE)),
            "layernorm_aliases_strictly_restored": alias_count,
            "save_reload_tensor_check": "passed",
        },
        "evaluation_threshold": 0.5,
        "metrics": {
            "multi_label_model": multi_metrics,
            "single_label_recovered_seed99_baseline_scored_against_same_label_sets": baseline_metrics,
        },
        "sourcewise_multi_label_metrics": source_metrics,
        "limitations": [
            "This is a new multi-label target definition; results are not directly comparable to single-label accuracy.",
            "All observed labels attached to the same company and cleaned narrative are unioned; this may preserve genuine cross-cutting tags but can also combine tags from reused boilerplate.",
            "Labels remain taxonomy-derived weak labels, including AI-assisted concept mappings; no independent human ground truth is available.",
            "The company-disjoint test partition has already been used in previous work; this is a re-evaluation on that established test, not a fresh external cohort.",
            "Source subsets can overlap when one company-text group aggregates labels from multiple sources.",
            "Hit@k ranking metrics and fixed-threshold F1 answer different questions; report both with their definitions.",
        ],
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("\nSTAGE 2 — MULTI-LABEL HELD-OUT EVALUATION")
    for name, metrics in (("Multi-label model", multi_metrics), ("Recovered single-label baseline", baseline_metrics)):
        print(f"{name}: Hit@1={metrics['hit_at_1']:.4f}; Hit@2={metrics['hit_at_2']:.4f}; micro-F1@0.5={metrics['micro_f1_at_0_5']:.4f}; macro-F1@0.5={metrics['macro_f1_at_0_5']:.4f}; exact-set={metrics['exact_set_match_at_0_5']:.4f}")
    print(f"Results: {REPORT_PATH}")
    print("Status: existing company-disjoint test re-evaluated; not a fresh test")


if __name__ == "__main__":
    main()
