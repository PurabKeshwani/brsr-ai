"""
Human Validation Study — Pearson Correlation (Phase: gap-fill for report's
stated methodology 5.5.3)

Computes the Pearson correlation coefficient between the AI-generated
Transparency Scores and independently-assigned human-readability/
disclosure-quality scores on a stratified 20-company sample (covering the
full AI-score range, 26.9-75.6 — see export_human_validation_sample.py).

DISCLOSURE: the human scores in this study were LLM-assisted (assigned by
reading each company's disclosure summary and rating overall quality),
not scored by an independent human ESG analyst blind to any AI output —
this must be stated plainly in the project report rather than presented
as equivalent to the report's originally stated methodology (which
implies independent human analysts). This is disclosed here in the code
so the distinction is not lost when this script's output is cited.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np
import pandas as pd
from scipy import stats

INPUT_PATH = Path("data/validation/human_score_validation.csv")


def main():
    df = pd.read_csv(INPUT_PATH)

    if df["human_score"].isnull().any() or (df["human_score"] == "").any():
        missing = df["human_score"].isnull().sum() + (df["human_score"] == "").sum()
        print(f"WARNING: {missing} rows have no human_score — excluding from analysis.")
        df = df[df["human_score"].notna() & (df["human_score"] != "")]

    df["human_score"] = df["human_score"].astype(float)
    df["ai_transparency_score"] = df["ai_transparency_score"].astype(float)

    n = len(df)
    print(f"Sample size: {n}")
    print(f"AI score range: {df['ai_transparency_score'].min():.1f} - {df['ai_transparency_score'].max():.1f}")
    print(f"Human score range: {df['human_score'].min():.1f} - {df['human_score'].max():.1f}")

    r, p_value = stats.pearsonr(df["ai_transparency_score"], df["human_score"])
    print(f"\nPearson correlation coefficient: r = {r:.4f}")
    print(f"p-value: {p_value:.6f}")
    print(f"Statistically significant at p<0.05: {p_value < 0.05}")
    print(f"Statistically significant at p<0.001: {p_value < 0.001}")

    r_squared = r ** 2
    print(f"R-squared (variance explained): {r_squared:.4f} ({r_squared*100:.1f}%)")

    # Spearman rank correlation as a robustness check — less sensitive to
    # outliers and doesn't assume linearity, useful given n=20
    rho, rho_p = stats.spearmanr(df["ai_transparency_score"], df["human_score"])
    print(f"\nSpearman rank correlation (robustness check): rho = {rho:.4f}, p = {rho_p:.6f}")

    print("\n=== Per-company comparison ===")
    df_sorted = df.sort_values("ai_transparency_score")
    for _, row in df_sorted.iterrows():
        diff = row["human_score"] - row["ai_transparency_score"]
        print(f"  {row['company_name']:<40} AI={row['ai_transparency_score']:>5.1f}  "
              f"Human={row['human_score']:>5.1f}  diff={diff:>+6.1f}")


if __name__ == "__main__":
    main()