"""Merge independently returned Stage 4 Batch 3 rater sheets for adjudication."""
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parents[2]
SHEET_DIR = BASE / "data/labeling_sheets"
PATH_A = SHEET_DIR / "stage4_batch3_rater_A.csv"
PATH_B = SHEET_DIR / "stage4_batch3_rater_B.csv"
OUT = SHEET_DIR / "stage4_batch3_clean.csv"


def main() -> None:
    a = pd.read_csv(PATH_A, dtype={"human_label": "string"})
    b = pd.read_csv(PATH_B, dtype={"human_label": "string"})
    keys = ["id", "company_name", "text"]
    for path, df in ((PATH_A, a), (PATH_B, b)):
        if not set(keys + ["human_label"]).issubset(df.columns):
            raise ValueError(f"{path} has missing required columns")
        if len(df) != 70 or df["id"].duplicated().any():
            raise ValueError(f"{path} must contain exactly 70 unique IDs")
        labels = df["human_label"].fillna("").str.strip()
        if labels.eq("").any() or not labels.isin(["0", "1"]).all():
            raise ValueError(f"{path} must have a 0/1 label for every row")

    a = a.sort_values("id").reset_index(drop=True)
    b = b.sort_values("id").reset_index(drop=True)
    if not a[keys].equals(b[keys]):
        raise ValueError("Rater sheets do not contain identical rows in identical ID order")

    merged = a[keys].copy()
    merged["human_label_rater_A"] = a["human_label"].astype(int)
    merged["human_label_rater_B"] = b["human_label"].astype(int)
    merged["adjudicated_label"] = ""
    merged.to_csv(OUT, index=False, encoding="utf-8-sig")
    disagreements = int((merged["human_label_rater_A"] != merged["human_label_rater_B"]).sum())
    print(f"Merged 70 rows to {OUT}; {disagreements} disagreements require adjudication.")
    print("Fill adjudicated_label for every row (including agreements) before held-out evaluation.")


if __name__ == "__main__":
    main()
