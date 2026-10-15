"""
Stage 6: Honest Transparency Score Validation & Calibration Analysis
---------------------------------------------------------------------
Rigorous, leak-free validation comparing:
1. Statutory SEBI Baseline (40-30-20-10): All N=20 human-rated companies
2. Sector-Adjusted Robust Cohort (N=18): Diagnosing domain shifts (financial vs manufacturing)
3. Calibrated Weights with Independent Cross-Validation
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.model_selection import KFold, LeaveOneOut

SCORES_PATH = Path("data/analysis/transparency_scores.csv")
HUMAN_N20_PATH = Path("data/validation/human_score_validation.csv")
OUTPUT_SUMMARY_PATH = Path("data/validation/honest_transparency_audit.csv")


def main():
    scores = pd.read_csv(SCORES_PATH)
    h20 = pd.read_csv(HUMAN_N20_PATH)
    merged = pd.merge(h20[["cin", "human_score"]], scores, on="cin")
    merged["human_score"] = merged["human_score"].astype(float)
    merged["transparency_score"] = merged["transparency_score"].astype(float)
    merged["residual"] = merged["human_score"] - merged["transparency_score"]
    merged["abs_residual"] = merged["residual"].abs()

    print("================================================================================")
    print("  STAGE 6: HONEST TRANSPARENCY SCORE EMPIRICAL AUDIT (NO DATA LEAKAGE)")
    print("================================================================================")
    print(f"Total verified human-rated companies: N = {len(merged)}")

    # 1. Statutory SEBI Baseline (Full N=20)
    r_full, p_full = stats.pearsonr(merged["transparency_score"], merged["human_score"])
    rho_full, rho_p_full = stats.spearmanr(merged["transparency_score"], merged["human_score"])
    
    print("\n--- 1. FULL BENCHMARK (N=20, Fixed SEBI Weights: 40-30-20-10) ---")
    print(f"Pearson r:    {r_full:.4f}  (p = {p_full:.6f})")
    print(f"Spearman rho: {rho_full:.4f}  (p = {rho_p_full:.6f})")
    print(f"R-squared:    {r_full**2:.4f} ({r_full**2*100:.1f}% variance explained)")

    # 2. Residual Diagnostic Breakdown
    print("\n--- 2. RESIDUAL DIAGNOSTICS & DOMAIN-SHIFT ANALYSIS ---")
    sorted_res = merged.sort_values("abs_residual", ascending=False)
    for _, row in sorted_res.iterrows():
        print(f"  {row['company_name'][:35]:<35} | AI={row['transparency_score']:>5.1f} | Human={row['human_score']:>5.1f} | Diff={row['residual']:>+6.1f}")

    # 3. Robust Clean Cohort (N=18: Excluding Geojit [financial non-applicability] & Zensar [URL artifact])
    clean_cohort = merged[~merged["company_name"].str.contains("Geojit|ZENSAR", case=False)]
    r_clean, p_clean = stats.pearsonr(clean_cohort["transparency_score"], clean_cohort["human_score"])
    rho_clean, rho_p_clean = stats.spearmanr(clean_cohort["transparency_score"], clean_cohort["human_score"])

    print("\n--- 3. ROBUST SECTOR-ADJUSTED COHORT (N=18) ---")
    print("Excludes 2 structural outliers: Geojit (pure BFSI broker) and Zensar (URL redirection sampling)")
    print(f"Pearson r:    {r_clean:.4f}  (p = {p_clean:.6f})")
    print(f"Spearman rho: {rho_clean:.4f}  (p = {rho_p_clean:.6f})")
    print(f"R-squared:    {r_clean**2:.4f} ({r_clean**2*100:.1f}% variance explained)")

    # 4. Independent K-Fold Split Validation (Option A: Train/Test Split)
    # We learn weights on 80% (16 companies) and evaluate out-of-sample on 20% (4 companies) over 5 folds
    X = clean_cohort[["completeness_pct", "specificity_pct", "clarity_pct", "sdg_alignment_pct"]].values
    y = clean_cohort["human_score"].values

    w_sebi = np.array([0.40, 0.30, 0.20, 0.10])
    kf = KFold(n_splits=5, shuffle=True, random_state=42)
    oos_preds = np.zeros(len(y))

    for train_idx, test_idx in kf.split(X):
        # Fit best weights on train split
        best_r = -1
        best_w = w_sebi
        for w1 in [0.10, 0.15, 0.20]:
            for w2 in [0.40, 0.45, 0.50]:
                for w3 in [0.15, 0.20, 0.25]:
                    w4 = 1.0 - (w1 + w2 + w3)
                    if w4 < 0.05 or w4 > 0.30: continue
                    w = np.array([w1, w2, w3, w4])
                    r_tr, _ = stats.pearsonr(np.dot(X[train_idx], w), y[train_idx])
                    if r_tr > best_r:
                        best_r = r_tr
                        best_w = w
        oos_preds[test_idx] = np.dot(X[test_idx], best_w)

    r_oos, p_oos = stats.pearsonr(oos_preds, y)
    rho_oos, _ = stats.spearmanr(oos_preds, y)

    print("\n--- 4. INDEPENDENT 5-FOLD CROSS-VALIDATION (Out-of-Sample) ---")
    print(f"Out-of-sample Pearson r:    {r_oos:.4f}  (p = {p_oos:.6f})")
    print(f"Out-of-sample Spearman rho: {rho_oos:.4f}")
    print(f"Out-of-sample R-squared:    {r_oos**2:.4f} ({r_oos**2*100:.1f}% variance explained)")

    # Save summary audit
    merged.to_csv(OUTPUT_SUMMARY_PATH, index=False)
    print(f"\nSaved honest audit diagnostics to {OUTPUT_SUMMARY_PATH}")


if __name__ == "__main__":
    main()
