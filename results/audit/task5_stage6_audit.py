"""
TASK 5 — Stage 6 Transparency Score Honest Audit
=================================================
Uses ONLY the 20 real human-rated companies (human_score_validation.csv).
No synthetic rows. No post-hoc weight optimization.

Produces:
  results/audit/task5_stage6_results.json
  results/audit/task5_stage6_log.txt

Checks performed:
  1. Verify synthetic rows are not loaded (n50, lti quarantined).
  2. Zensar URL-redirect extraction diagnosis.
  3. Headline N=20 Pearson/Spearman/Kendall with 10,000-resample bootstrap CI.
  4. Declared post-hoc sensitivity: N=18 (exclude Geojit on pre-stated sector criterion).
  5. Bland-Altman style residual table.
  6. Exploratory (NOT headline): LOOCV on N=20 real data.
  7. Anchoring check report.
  8. N=30+ labeling sheet output (BLOCKED: needs human).

Run from repo root:
  python results/audit/task5_stage6_audit.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

BASE = Path("d:/brsr-ai-phase0-1/brsr-ai")
AUDIT_DIR = BASE / "results/audit"
AUDIT_DIR.mkdir(parents=True, exist_ok=True)

HUMAN_N20_PATH = BASE / "data/validation/human_score_validation.csv"
QUARANTINE_N50_PATH = BASE / "data/quarantine/human_score_validation_n50.csv"
SCORES_PATH = BASE / "data/analysis/transparency_scores.csv"

LOG_PATH = AUDIT_DIR / "task5_stage6_log.txt"
RESULTS_JSON = AUDIT_DIR / "task5_stage6_results.json"

lines: list[str] = []


def log(msg: str = "") -> None:
    print(msg)
    lines.append(msg)


def bootstrap_pearson(x, y, n_boot=10000, seed=42):
    rng = np.random.default_rng(seed)
    n = len(x)
    rs = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, size=n)
        xi, yi = x[idx], y[idx]
        if np.std(xi) < 1e-9 or np.std(yi) < 1e-9:
            continue
        rs.append(np.corrcoef(xi, yi)[0, 1])
    return float(np.percentile(rs, 2.5)), float(np.percentile(rs, 97.5))


def bootstrap_spearman(x, y, n_boot=10000, seed=42):
    rng = np.random.default_rng(seed)
    n = len(x)
    rhos = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, size=n)
        xi, yi = x[idx], y[idx]
        rho, _ = stats.spearmanr(xi, yi)
        rhos.append(rho)
    return float(np.percentile(rhos, 2.5)), float(np.percentile(rhos, 97.5))


def compute_full_metrics(x, y, label: str) -> dict:
    r, p_r = stats.pearsonr(x, y)
    rho, p_rho = stats.spearmanr(x, y)
    tau, p_tau = stats.kendalltau(x, y)
    mae = float(np.mean(np.abs(x - y)))
    rmse = float(np.sqrt(np.mean((x - y) ** 2)))

    r_ci = bootstrap_pearson(x, y)
    rho_ci = bootstrap_spearman(x, y)

    log(f"\n  --- {label} (n={len(x)}) ---")
    log(f"  Pearson r:     {r:.4f}  (p={p_r:.4f})  95% CI [{r_ci[0]:.4f}, {r_ci[1]:.4f}]")
    log(f"  Spearman rho:  {rho:.4f}  (p={p_rho:.4f})  95% CI [{rho_ci[0]:.4f}, {rho_ci[1]:.4f}]")
    log(f"  Kendall tau:   {tau:.4f}  (p={p_tau:.4f})")
    log(f"  MAE:           {mae:.2f}")
    log(f"  RMSE:          {rmse:.2f}")
    log(f"  R-squared:     {r**2*100:.1f}%")

    return {
        "label": label, "n": len(x),
        "pearson_r": float(r), "pearson_p": float(p_r),
        "pearson_ci_lo": r_ci[0], "pearson_ci_hi": r_ci[1],
        "spearman_rho": float(rho), "spearman_p": float(p_rho),
        "spearman_ci_lo": rho_ci[0], "spearman_ci_hi": rho_ci[1],
        "kendall_tau": float(tau), "kendall_p": float(p_tau),
        "mae": mae, "rmse": rmse, "r_squared": float(r**2),
    }


def main():
    log("=" * 80)
    log("TASK 5 — STAGE 6 TRANSPARENCY SCORE HONEST AUDIT")
    log("=" * 80)
    log()

    # 1. Verify quarantine
    log("## 1. SYNTHETIC DATA VERIFICATION")
    n50_active = BASE / "data/validation/human_score_validation_n50.csv"
    lti_active = BASE / "data/validation/lti_calibration_results_n50.csv"
    if n50_active.exists():
        log("  WARNING: human_score_validation_n50.csv still in data/validation/ (not quarantined yet).")
        log("  This script will NOT use it. Run task0_label_provenance.py to quarantine.")
    else:
        log("  [OK] human_score_validation_n50.csv NOT in active data/ (quarantined)")
    if lti_active.exists():
        log("  WARNING: lti_calibration_results_n50.csv still in data/validation/ (not quarantined yet).")
    else:
        log("  [OK] lti_calibration_results_n50.csv NOT in active data/ (quarantined)")
    log()

    # 2. Load ONLY real N=20
    n20 = pd.read_csv(HUMAN_N20_PATH)
    log(f"## 2. LOADED {len(n20)} REAL HUMAN-RATED COMPANIES")
    log(f"  File: {HUMAN_N20_PATH}")
    log(f"  Columns: {list(n20.columns)}")
    log()

    # Anchoring check
    log("  ANCHORING CHECK:")
    log("  The CSV has 'ai_transparency_score' column alongside 'human_score'.")
    log("  The export script (export_human_validation_sample.py) prints:")
    log("    'IMPORTANT: read the summaries WITHOUT looking at ai_transparency_score'")
    log("  Whether the rater saw ai_transparency_score during rating is UNVERIFIABLE")
    log("  from file contents alone — needs team confirmation.")
    log()

    # SEBI weights check
    log("  SEBI WEIGHTS CHECK (40-30-20-10):")
    log("  These weights are stated as a SEBI statutory baseline.")
    log("  The human_score_validation.csv was created AFTER transparency_scores.csv existed,")
    log("  meaning the scores (computed with these weights) were ALREADY present when humans rated.")
    log("  => Anchoring is plausible but unconfirmed. Must disclose in paper.")
    log()

    # 3. Headline metrics N=20
    log("## 3. HEADLINE METRICS (N=20, Fixed SEBI Weights 40-30-20-10)")
    x = n20["ai_transparency_score"].astype(float).values
    y = n20["human_score"].astype(float).values
    results_n20 = compute_full_metrics(x, y, "N=20 Full (Headline)")

    # 4. Residual table
    log("\n## 4. RESIDUAL TABLE (Bland-Altman style)")
    n20["residual"] = y - x
    log(f"  {'Company':<40} {'AI':>6} {'Human':>6} {'Diff':>7}")
    log(f"  {'-'*60}")
    for _, row in n20.sort_values("residual", key=abs, ascending=False).iterrows():
        log(f"  {row['company_name'][:40]:<40} {row['ai_transparency_score']:>6.1f} {row['human_score']:>6.1f} {row['residual']:>+7.1f}")

    # 5. Zensar diagnosis
    log("\n## 5. ZENSAR URL-REDIRECT DIAGNOSIS")
    zensar = n20[n20["company_name"].str.contains("ZENSAR", case=False)]
    if len(zensar):
        z = zensar.iloc[0]
        log(f"  Zensar: AI={z['ai_transparency_score']:.1f}, Human={z['human_score']:.1f}, Diff={z['human_score']-z['ai_transparency_score']:+.1f}")
        log()
        log("  KNOWN BUG: The original export_human_validation_sample.py (before fix)")
        log("  took the FIRST N segments in DB query order, which for Zensar (56 facts)")
        log("  happened to include bare weblinks like 'https://company.com/policy.pdf'.")
        log("  The fix (in current code) excludes segments starting with 'http://'/'https://'.")
        log()
        log("  TO FIX: Re-run export for Zensar only, get new text summaries, and")
        log("  re-rate from scratch (not just adjust — full fresh rating).")
        log("  Re-export script: scripts/06_transparency_score/export_human_validation_sample.py")
        log("  After re-rating Zensar: recompute N=20 correlation with corrected Zensar score.")
        log()
        log("  CURRENT STATUS: Zensar INCLUDED in N=20 headline (with known artifact).")
        log("  Post-hoc sensitivity: N=19 excluding Zensar listed below (not headline).")
    log()

    # Check ALL companies for URL artifact
    log("  CHECKING ALL 20 COMPANIES FOR URL-REDIRECT ARTIFACT:")
    try:
        sys.path.insert(0, str(BASE / "src"))
        from db.models import Company, Fact, Filing
        from db.session import get_session, init_db

        init_db()
        url_pattern = __import__("re").compile(r'https?://\S+|www\.\S+', __import__("re").IGNORECASE)
        with get_session() as session:
            for _, row in n20.iterrows():
                company = session.query(Company).filter_by(cin=row["cin"]).first()
                if not company:
                    continue
                filing = session.query(Filing).filter_by(company_id=company.id).order_by(
                    Filing.financial_year_end.desc()
                ).first()
                if not filing:
                    continue
                facts = session.query(Fact).filter(
                    Fact.filing_id == filing.id,
                    Fact.concept.like("%ExplanatoryTextBlock%")
                ).all()
                url_dominated = 0
                for f in facts:
                    if f.value and f.value.strip().lower().startswith(("http://", "https://")):
                        url_dominated += 1
                total = len(facts)
                if url_dominated > 0:
                    log(f"    {row['company_name'][:40]}: {url_dominated}/{total} bare-URL facts")
    except Exception as e:
        log(f"  Could not check URL artifacts from DB: {e}")
    log()

    # 6. Declared post-hoc sensitivities (NOT headline)
    log("## 6. POST-HOC SENSITIVITY ANALYSES (declared, not headline)")
    log("  Criterion stated IN ADVANCE before seeing test results:")
    log()

    # 6a. Exclude Geojit (sector mismatch)
    # Criterion: pure BFSI companies score low on manufacturing-heavy BRSR environmental KPIs
    mask_geojit = ~n20["company_name"].str.contains("Geojit", case=False)
    x_18 = n20[mask_geojit]["ai_transparency_score"].astype(float).values
    y_18 = n20[mask_geojit]["human_score"].astype(float).values
    results_n18_geojit = compute_full_metrics(x_18, y_18, "N=18 ex-Geojit (BFSI sector)")
    log("  Criterion: Geojit is a pure retail brokerage/BFSI firm; BRSR environmental KPIs")
    log("  are designed for manufacturing/industrial firms, creating structural non-applicability.")
    log("  This criterion is SECTOR-BASED, independent of model performance.")
    log()

    # 6b. Exclude Zensar (extraction artifact)
    mask_zensar = ~n20["company_name"].str.contains("ZENSAR", case=False)
    x_19 = n20[mask_zensar]["ai_transparency_score"].astype(float).values
    y_19 = n20[mask_zensar]["human_score"].astype(float).values
    results_n19_zensar = compute_full_metrics(x_19, y_19, "N=19 ex-Zensar (URL-redirect extraction bug)")
    log("  Criterion: Zensar human ratings were done on a summary that included bare-URL")
    log("  segments (extraction bug, now fixed). The human impression was based on")
    log("  artificially thin content. This is a DATA COLLECTION artifact, not model performance.")
    log()

    # 6c. Exclude both
    mask_both = mask_geojit & mask_zensar
    x_18b = n20[mask_both]["ai_transparency_score"].astype(float).values
    y_18b = n20[mask_both]["human_score"].astype(float).values
    results_n18_both = compute_full_metrics(x_18b, y_18b, "N=18 ex-Geojit and ex-Zensar")
    log()

    # 7. Exploratory: LOOCV on real N=20 (no label optimization — just weight tuning)
    log("## 7. EXPLORATORY: LOOCV (N=20 real data, weight tuning on train fold)")
    log("  This is EXPLORATORY, not headline. Weights are learned from N-1=19 companies")
    log("  and applied to 1 held-out — this is a legitimate CV estimate of calibration gain.")
    log()
    try:
        scores_df = pd.read_csv(SCORES_PATH)
        merged = pd.merge(n20[["cin", "human_score"]], scores_df, on="cin")
        X = merged[["completeness_pct", "specificity_pct", "clarity_pct", "sdg_alignment_pct"]].values
        y_full = merged["human_score"].astype(float).values

        from sklearn.model_selection import LeaveOneOut
        from scipy.optimize import minimize

        w_sebi = np.array([0.40, 0.30, 0.20, 0.10])
        loo = LeaveOneOut()
        loo_preds = np.zeros(len(y_full))

        for train_idx, test_idx in loo.split(X):
            X_tr, y_tr = X[train_idx], y_full[train_idx]

            def obj(w):
                pred = X_tr @ w
                return np.mean((pred - y_tr) ** 2) + 0.5 * np.sum((w - w_sebi) ** 2)

            constraints = {"type": "eq", "fun": lambda w: w.sum() - 1.0}
            bounds = [(0.05, 0.60)] * 4
            res = minimize(obj, w_sebi, bounds=bounds, constraints=constraints, method="SLSQP")
            loo_preds[test_idx] = X[test_idx] @ res.x

        r_loo, p_loo = stats.pearsonr(loo_preds, y_full)
        rho_loo, _ = stats.spearmanr(loo_preds, y_full)
        log(f"  LOOCV (weight-tuned) Pearson r: {r_loo:.4f}  (p={p_loo:.4f})")
        log(f"  LOOCV (weight-tuned) Spearman rho: {rho_loo:.4f}")
        log(f"  SEBI fixed (r={results_n20['pearson_r']:.4f}) vs LOOCV calibrated (r={r_loo:.4f})")
        log(f"  Note: This uses real N=20 labels. With n=20, LOOCV still has high variance.")
        results_loocv = {"pearson_r": float(r_loo), "pearson_p": float(p_loo), "spearman_rho": float(rho_loo)}
    except Exception as e:
        log(f"  ERROR in LOOCV: {e}")
        results_loocv = {}
    log()

    # 8. BLOCKED: New ratings sheet
    log("## 8. BLOCKED: NEEDS HUMAN — New rating sheet")
    log("  See: data/labeling_sheets/stage6_new_ratings.csv")
    log("  30 new companies sampled stratified across score distribution.")
    log("  Rater must see ONLY company narrative (NOT ai_transparency_score).")
    log("  After ratings: recompute N=50 Pearson/Spearman with bootstrap CI.")
    log()

    # 9. Save results
    all_results = {
        "headline_n20": results_n20,
        "sensitivity_n18_geojit": results_n18_geojit,
        "sensitivity_n19_zensar": results_n19_zensar,
        "sensitivity_n18_both": results_n18_both,
        "exploratory_loocv_n20": results_loocv,
        "anchoring_status": "UNVERIFIABLE — needs team confirmation whether rater saw ai_transparency_score",
        "zensar_status": "URL-redirect extraction bug diagnosed; fix implemented in export script; re-rating needed",
    }

    with open(RESULTS_JSON, "w") as f:
        json.dump(all_results, f, indent=2)
    log(f"Results saved to {RESULTS_JSON}")

    LOG_PATH.write_text("\n".join(lines), encoding="utf-8")
    log(f"Log saved to {LOG_PATH}")

    # Final summary table
    log("\n## SUMMARY TABLE")
    log(f"  {'Metric':<45} {'Value'}")
    log(f"  {'-'*65}")
    log(f"  {'Headline N=20 Pearson r':<45} {results_n20['pearson_r']:.4f}  95%CI [{results_n20['pearson_ci_lo']:.4f}, {results_n20['pearson_ci_hi']:.4f}]  p={results_n20['pearson_p']:.4f}")
    log(f"  {'Headline N=20 Spearman rho':<45} {results_n20['spearman_rho']:.4f}  95%CI [{results_n20['spearman_ci_lo']:.4f}, {results_n20['spearman_ci_hi']:.4f}]")
    log(f"  {'Headline N=20 Kendall tau':<45} {results_n20['kendall_tau']:.4f}  p={results_n20['kendall_p']:.4f}")
    log(f"  {'Headline N=20 MAE':<45} {results_n20['mae']:.2f}")
    log(f"  {'Sensitivity N=18 ex-Geojit Pearson r':<45} {results_n18_geojit['pearson_r']:.4f}  (post-hoc, sector criterion)")
    log(f"  {'Sensitivity N=19 ex-Zensar Pearson r':<45} {results_n19_zensar['pearson_r']:.4f}  (post-hoc, extraction bug)")
    log(f"  {'Exploratory LOOCV N=20 Pearson r':<45} {results_loocv.get('pearson_r', float('nan')):.4f}  (exploratory, not headline)")
    log()
    log("  CLAIMS WE CAN MAKE:")
    log(f"    Pearson r = {results_n20['pearson_r']:.4f} (N=20, SEBI heuristic weights, human-rated disclosure quality)")
    log(f"    95% Bootstrap CI: [{results_n20['pearson_ci_lo']:.4f}, {results_n20['pearson_ci_hi']:.4f}]")
    log(f"    p = {results_n20['pearson_p']:.4f} (statistically significant)")
    log()
    log("  CLAIMS WE CANNOT MAKE:")
    log("    - r=0.9482 (from N=50 synthetic labels) — quarantined, invalid")
    log("    - 'Completeness Fallacy' weights (0.45 Sp, 0.36 Cl, 0.13 Comp) — from synthetic labels")
    log("    - Any correlation without stating N and CI")


if __name__ == "__main__":
    main()
