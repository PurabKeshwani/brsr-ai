"""Reconcile the active Stage 2 dataset and prepare a blinded Section C review.

Read-only inputs: data/training/{train,val,test}.csv
Outputs: data/labeling_sheets/stage2_mapping_audit/{rater_sheet,answer_key}.csv

Give only rater_sheet.csv to the domain expert. Keep answer_key.csv private
until the expert has completed their labels. This script does not train models
or modify the active dataset.
"""
from __future__ import annotations

import csv
import hashlib
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPLITS = ("train", "val", "test")
SAMPLE_PER_PRINCIPLE = 23
SEED = 42
OUT_DIR = ROOT / "data" / "labeling_sheets" / "stage2_mapping_audit"


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_rows(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    split_rows = {name: read_rows(ROOT / "data" / "training" / f"{name}.csv") for name in SPLITS}
    required = {"text", "label", "principle_id", "cin", "source"}
    for name, rows in split_rows.items():
        if not rows or not required.issubset(rows[0]):
            raise ValueError(f"{name}.csv is empty or missing columns: {sorted(required)}")

    all_rows = [row for name in SPLITS for row in split_rows[name]]
    source_by_split = {
        split: dict(sorted(Counter(row["source"] for row in rows).items()))
        for split, rows in split_rows.items()
    }
    source_totals = dict(sorted(Counter(row["source"] for row in all_rows).items()))
    report = {
        "dataset": "data/training/{train,val,test}.csv",
        "split_rows": {split: len(split_rows[split]) for split in SPLITS},
        "total_rows": len(all_rows),
        "source_rows_by_split": source_by_split,
        "source_rows_total": source_totals,
        "split_sum_matches_total": sum(len(split_rows[s]) for s in SPLITS) == len(all_rows),
        "unique_cins_by_split": {s: len({r["cin"] for r in split_rows[s]}) for s in SPLITS},
    }

    section_c_by_principle: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in all_rows:
        if row["source"] == "section_c":
            section_c_by_principle[row["principle_id"]].append(row)

    rng = random.Random(SEED)
    chosen: list[tuple[str, dict[str, str]]] = []
    for principle in sorted(section_c_by_principle):
        pool = section_c_by_principle[principle]
        sample = rng.sample(pool, min(SAMPLE_PER_PRINCIPLE, len(pool)))
        chosen.extend((principle, row) for row in sample)
    rng.shuffle(chosen)

    rater_rows = []
    key_rows = []
    for row_id, (principle, row) in enumerate(chosen, start=1):
        digest = hashlib.sha256(row["text"].encode("utf-8")).hexdigest()
        rater_rows.append({"id": str(row_id), "text": row["text"], "human_label": "", "notes": ""})
        key_rows.append({
            "id": str(row_id),
            "cin": row["cin"],
            "company_name": row.get("company_name", ""),
            "source": row["source"],
            "principle_id": principle,
            "system_label": row["label"],
            "text_sha256": digest,
        })

    report["spot_check"] = {
        "seed": SEED,
        "rows": len(chosen),
        "rows_by_principle": dict(sorted(Counter(p for p, _ in chosen).items())),
        "rater_file": "data/labeling_sheets/stage2_mapping_audit/rater_sheet.csv",
        "private_key_file": "data/labeling_sheets/stage2_mapping_audit/answer_key.csv",
        "instructions": "Give only rater_sheet.csv to the expert; keep answer_key.csv private until labels are complete.",
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    write_rows(OUT_DIR / "rater_sheet.csv", rater_rows, ["id", "text", "human_label", "notes"])
    write_rows(
        OUT_DIR / "answer_key.csv",
        key_rows,
        ["id", "cin", "company_name", "source", "principle_id", "system_label", "text_sha256"],
    )
    (OUT_DIR / "reconciliation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
