"""Create separate blind Batch 3 labeling sheets for two independent raters."""
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parents[2]
SOURCE = BASE / "data/labeling_sheets/stage4_batch3_clean.csv"
OUT_DIR = BASE / "data/labeling_sheets"


def main() -> None:
    df = pd.read_csv(SOURCE)
    needed = {"id", "company_name", "text"}
    if not needed.issubset(df.columns):
        raise ValueError(f"Source sheet needs columns: {sorted(needed)}")
    if len(df) != 70:
        raise ValueError(f"Expected 70 Batch 3 examples, found {len(df)}")
    if df["id"].duplicated().any() or df["text"].fillna("").astype(str).str.strip().duplicated().any():
        raise ValueError("Duplicate row IDs or text found in Batch 3 sheet")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for rater in ("A", "B"):
        sheet = df[["id", "company_name", "text"]].copy()
        sheet["human_label"] = ""
        path = OUT_DIR / f"stage4_batch3_rater_{rater}.csv"
        sheet.to_csv(path, index=False, encoding="utf-8-sig")
        print(f"Written {path} ({len(sheet)} rows; no model predictions or signals)")
    print("Give each file only to its named rater; raters must not see each other's labels.")


if __name__ == "__main__":
    main()
