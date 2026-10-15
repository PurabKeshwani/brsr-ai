"""
Generates all numbers and figures needed for the three Results sub-sections
of the GRASP paper:
  1. Company-wise Transparency Score (detailed breakdown for one company)
  2. Sector-wise Transparency Score Comparison (top 15 reliable sectors, sorted)
  3. Intra-Sector Company Comparison (Chemicals Manufacturing, all companies)

Outputs:
  data/analysis/paper_company_breakdown.csv   – single-company detail
  data/analysis/paper_sector_comparison.csv   – sector-level table
  data/analysis/paper_intrasector.csv         – intra-sector company table

Run from the project root:
    python3 scripts/07_reporting/paper_results_analysis.py
"""
import csv
import statistics
from pathlib import Path

import pandas as pd

SCORES_PATH   = Path("data/analysis/transparency_scores.csv")
BENCHMARKS_PATH = Path("data/analysis/sector_benchmarks.csv")
SECTOR_PATH   = Path("data/analysis/sector_summary.csv")

OUT_COMPANY   = Path("data/analysis/paper_company_breakdown.csv")
OUT_SECTOR    = Path("data/analysis/paper_sector_comparison.csv")
OUT_INTRA     = Path("data/analysis/paper_intrasector.csv")

# ─────────────────────────────────────────────────────────────
# 1. Load data
# ─────────────────────────────────────────────────────────────
scores      = pd.read_csv(SCORES_PATH)
benchmarks  = pd.read_csv(BENCHMARKS_PATH)
sector_sum  = pd.read_csv(SECTOR_PATH)

print(f"Loaded {len(scores)} scored companies, {len(sector_sum)} sectors")

# ─────────────────────────────────────────────────────────────
# 2. Global distribution
# ─────────────────────────────────────────────────────────────
ts = scores["transparency_score"]
print(f"\n=== Global Distribution (n={len(scores)}) ===")
print(f"  Min    : {ts.min():.2f}   ({scores.loc[ts.idxmin(), 'company_name']})")
print(f"  Max    : {ts.max():.2f}   ({scores.loc[ts.idxmax(), 'company_name']})")
print(f"  Mean   : {ts.mean():.2f}")
print(f"  Median : {ts.median():.2f}")
print(f"  Std Dev: {ts.std():.2f}")

# ─────────────────────────────────────────────────────────────
# 3. OUTPUT 1 – Single-company breakdown
#    Pick a well-known company with median-ish score and all
#    four components available — choose Triveni Turbine Limited
#    (score=68.91, sector=Machinery and Equipment, percentile=94.4)
#    which is an identifiable, real company in the dataset.
# ─────────────────────────────────────────────────────────────
TARGET_COMPANY = "Triveni Turbine Limited"

co = scores[scores["company_name"] == TARGET_COMPANY].iloc[0]
bench_co = benchmarks[benchmarks["company_name"] == TARGET_COMPANY].iloc[0]

print(f"\n=== Company: {TARGET_COMPANY} ===")
print(f"  CIN                  : {co['cin']}")
print(f"  Sector               : {bench_co['sector']}")
print(f"  Completeness (40%)   : {co['completeness_pct']:.2f}%")
print(f"  Specificity (30%)    : {co['specificity_pct']:.2f}%")
print(f"  Clarity (20%)        : {co['clarity_pct']:.2f}%")
print(f"  SDG Alignment (10%)  : {co['sdg_alignment_pct']:.2f}%")
print(f"  Transparency Score   : {co['transparency_score']:.2f}")
print(f"  Narrative segments   : {co['total_narrative_segments']}")
print(f"  Sector mean          : {bench_co['sector_mean']:.2f}")
print(f"  Sector median        : {bench_co['sector_median']:.2f}")
print(f"  Sector peer count    : {bench_co['sector_peer_count']}")
print(f"  Percentile rank      : {bench_co['percentile_rank']:.1f}")
print(f"  Is sector leader     : {bench_co['is_sector_leader']}")

# Verify composite manually
manual_ts = (0.40 * co['completeness_pct']
             + 0.30 * co['specificity_pct']
             + 0.20 * co['clarity_pct']
             + 0.10 * co['sdg_alignment_pct'])
print(f"  Manual verify TS     : {manual_ts:.2f}  (matches: {abs(manual_ts - co['transparency_score']) < 0.02})")

company_rows = [{
    "field": "Company Name",      "value": TARGET_COMPANY},
    {"field": "CIN",              "value": co['cin']},
    {"field": "Sector",           "value": bench_co['sector']},
    {"field": "Completeness (40% weight)",    "value": f"{co['completeness_pct']:.1f}%"},
    {"field": "Specificity (30% weight)",     "value": f"{co['specificity_pct']:.1f}%"},
    {"field": "Clarity (20% weight)",         "value": f"{co['clarity_pct']:.1f}%"},
    {"field": "SDG Alignment (10% weight)",   "value": f"{co['sdg_alignment_pct']:.1f}%"},
    {"field": "Transparency Score",           "value": f"{co['transparency_score']:.2f}"},
    {"field": "Narrative Segments Analyzed",  "value": str(int(co['total_narrative_segments']))},
    {"field": "Sector Mean Score",            "value": f"{bench_co['sector_mean']:.2f}"},
    {"field": "Sector Peer Count",            "value": str(int(bench_co['sector_peer_count']))},
    {"field": "Sector Percentile Rank",       "value": f"{bench_co['percentile_rank']:.1f}th"},
]
pd.DataFrame(company_rows).to_csv(OUT_COMPANY, index=False)
print(f"\nWritten: {OUT_COMPANY}")

# ─────────────────────────────────────────────────────────────
# 4. OUTPUT 2 – Sector-wise comparison
#    Use only reliable sectors (>=5 companies), sorted by mean score desc
# ─────────────────────────────────────────────────────────────
reliable_sectors = (sector_sum[sector_sum["reliable"] == True]
                    .sort_values("mean_score", ascending=False)
                    .reset_index(drop=True))

print(f"\n=== Reliable Sectors: {len(reliable_sectors)} ===")
print(reliable_sectors[["sector","company_count","mean_score","median_score","min_score","max_score","std_dev"]].to_string())

# Save top 15 for the paper table
top15 = reliable_sectors.head(15)
top15.to_csv(OUT_SECTOR, index=False)
print(f"\nWritten: {OUT_SECTOR}")

# ─────────────────────────────────────────────────────────────
# 5. OUTPUT 3 – Intra-sector comparison
#    Use Chemicals Manufacturing (n=101, largest reliable sector)
# ─────────────────────────────────────────────────────────────
INTRA_SECTOR = "Chemicals Manufacturing"
sector_cos = (benchmarks[benchmarks["sector"] == INTRA_SECTOR]
              .sort_values("transparency_score", ascending=False)
              .reset_index(drop=True))

print(f"\n=== Intra-Sector: {INTRA_SECTOR} (n={len(sector_cos)}) ===")
print("Top 10:")
print(sector_cos.head(10)[["company_name","transparency_score","percentile_rank","is_sector_leader"]].to_string())
print("\nBottom 5:")
print(sector_cos.tail(5)[["company_name","transparency_score","percentile_rank","is_sector_laggard"]].to_string())

# For chart: top 8 + bottom 8
top8 = sector_cos.head(8)
bot8 = sector_cos.tail(8)
chart_cos = pd.concat([top8, bot8]).drop_duplicates()

# Merge in component scores
chart_cos = chart_cos.merge(
    scores[["company_name","completeness_pct","specificity_pct","clarity_pct","sdg_alignment_pct","total_narrative_segments"]],
    on="company_name", how="left"
)

print("\nChart companies (top 8 + bottom 8):")
print(chart_cos[["company_name","transparency_score","percentile_rank"]].to_string())

chart_cos.to_csv(OUT_INTRA, index=False)
print(f"\nWritten: {OUT_INTRA}")

# ─────────────────────────────────────────────────────────────
# 6. Additional: find a "representative mid-range" company
#    for a richer narrative if needed
# ─────────────────────────────────────────────────────────────
med = ts.median()
mid = (scores.assign(dist=abs(scores["transparency_score"] - med))
       .sort_values("dist").head(5))
print(f"\nCompanies closest to median ({med:.2f}):")
print(mid[["company_name","transparency_score","total_narrative_segments"]].to_string())

print("\nDone.")
