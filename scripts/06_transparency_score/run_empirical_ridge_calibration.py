"""
Empirical Calibration & Ridge Weight Optimization for Transparency Score (Stage 6)

Compares:
1. Baseline SEBI Heuristic Weights (40% Completeness, 30% Specificity, 20% Clarity, 10% SDG): r = 0.6314
2. Statistically Calibrated Weights (Ridge / Non-negative Least Squares): finds the empirical optimal
   weighting that maximizes correlation with expert disclosure quality ratings.
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.linear_model import Ridge, ElasticNet
from sklearn.model_selection import LeaveOneOut
from scipy.optimize import nnls

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

SCORES_PATH = Path("data/analysis/transparency_scores.csv")
HUMAN_PATH = Path("data/validation/human_score_validation.csv")


def main():
    scores_df = pd.read_csv(SCORES_PATH)
    human_df = pd.read_csv(HUMAN_PATH)

    merged = pd.merge(human_df[["cin", "human_score"]], scores_df, on="cin")
    print(f"Loaded {len(merged)} companies with paired human ratings and component scores.")

    X = merged[["completeness_pct", "specificity_pct", "clarity_pct", "sdg_alignment_pct"]].values
    y = merged["human_score"].values
    baseline_ai = merged["transparency_score"].values

    # Baseline correlation
    r_base, p_base = stats.pearsonr(baseline_ai, y)
    rho_base, _ = stats.spearmanr(baseline_ai, y)
    print("\n=== BASELINE HEURISTIC WEIGHTS (40-30-20-10) ===")
    print(f"Pearson r:  {r_base:.4f}  (p = {p_base:.6f})")
    print(f"Spearman rho: {rho_base:.4f}")
    print(f"R-squared:  {r_base**2:.4f} ({r_base**2*100:.1f}%)")

    # Non-negative normalized least squares to learn optimal component weights
    # Constrain weights to sum to 1.0 and be non-negative
    weights_raw, _ = nnls(X, y)
    weights_norm = weights_raw / sum(weights_raw)

    print("\n=== EMPIRICALLY CALIBRATED WEIGHTS (Non-Negative Least Squares) ===")
    comp_names = ["Completeness (C)", "Specificity (Sp)", "Clarity (Cl)", "SDG Alignment (SDG)"]
    for name, w_orig, w_opt in zip(comp_names, [0.40, 0.30, 0.20, 0.10], weights_norm):
        print(f"  {name:<25}: SEBI={w_orig:.2f} -> Calibrated={w_opt:.3f}")

    # Compute calibrated score with LOOCV
    loo = LeaveOneOut()
    calibrated_preds = np.zeros(len(y))

    for train_idx, test_idx in loo.split(X):
        w, _ = nnls(X[train_idx], y[train_idx])
        w = w / max(sum(w), 1e-6)
        calibrated_preds[test_idx] = np.dot(X[test_idx], w)

    r_opt, p_opt = stats.pearsonr(calibrated_preds, y)
    rho_opt, _ = stats.spearmanr(calibrated_preds, y)

    print("\n=== CROSS-VALIDATED (LOOCV) CALIBRATED TRANSPARENCY SCORE ===")
    print(f"Pearson r:  {r_opt:.4f}  (p = {p_opt:.6f})")
    print(f"Spearman rho: {rho_opt:.4f}")
    print(f"R-squared:  {r_opt**2:.4f} ({r_opt**2*100:.1f}%)")
    print(f"Correlation improvement: {r_base:.4f} -> {r_opt:.4f} (gain: +{r_opt - r_base:.4f})")


if __name__ == "__main__":
    main()
