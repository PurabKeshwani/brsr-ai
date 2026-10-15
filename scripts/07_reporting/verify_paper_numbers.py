"""
Final verification: checks every number in the three new Results sub-sections
against the actual CSV data and flags any discrepancy.
"""
import pandas as pd
import sys

OK  = "[OK] "
FAIL = "[FAIL] "
errors = 0

scores     = pd.read_csv('data/analysis/transparency_scores.csv')
benchmarks = pd.read_csv('data/analysis/sector_benchmarks.csv')
sector_sum = pd.read_csv('data/analysis/sector_summary.csv')

def check(cond, msg):
    global errors
    tag = OK if cond else FAIL
    if not cond:
        errors += 1
    print(tag + msg)

# ── Global distribution ──────────────────────────────────────────────────────
ts = scores['transparency_score']
check(abs(ts.min() - 26.88) < 0.01, "Global min = 26.88")
check(abs(ts.max() - 75.58) < 0.01, "Global max = 75.58")
check(abs(ts.median() - 47.25) < 0.01, "Global median = 47.25")
check(abs(ts.mean() - 48.73) < 0.02, f"Global mean ~= 48.73 (actual {ts.mean():.2f})")

rel = sector_sum[sector_sum['reliable']==True]
check(len(rel) == 47, f"47 reliable sectors (actual {len(rel)})")
unreliable = sector_sum[sector_sum['reliable']==False]
check(len(unreliable) == 25, f"25 smaller sectors (actual {len(unreliable)}, total={len(sector_sum)})")

# ── Output 1: Triveni Turbine Limited ────────────────────────────────────────
co = scores[scores['company_name']=='Triveni Turbine Limited'].iloc[0]
bc = benchmarks[benchmarks['company_name']=='Triveni Turbine Limited'].iloc[0]
check(abs(co['completeness_pct'] - 57.99) < 0.01, "Triveni Completeness = 57.99%")
check(abs(co['specificity_pct']  - 63.46) < 0.01, "Triveni Specificity = 63.46%")
check(abs(co['clarity_pct']      - 98.08) < 0.01, "Triveni Clarity = 98.08%")
check(abs(co['sdg_alignment_pct']- 70.59) < 0.01, "Triveni SDG Alignment = 70.59%")
check(abs(co['transparency_score'] - 68.91) < 0.01, "Triveni TS = 68.91")
check(int(co['total_narrative_segments']) == 52, "Triveni segments = 52")
check(bc['sector'] == 'Machinery and Equipment', f"Triveni sector = 'Machinery and Equipment' (got '{bc['sector']}')")
check(int(bc['sector_peer_count']) == 36, f"Triveni peer count = 36 (got {bc['sector_peer_count']})")
check(abs(bc['percentile_rank'] - 94.4) < 0.1, f"Triveni percentile = 94.4 (got {bc['percentile_rank']})")
check(abs(bc['sector_mean'] - 49.46) < 0.01, f"Triveni sector mean = 49.46 (got {bc['sector_mean']})")

# Verify formula manually
manual = 0.40*57.99 + 0.30*63.46 + 0.20*98.08 + 0.10*70.59
check(abs(manual - 68.91) < 0.02, f"Manual formula = 68.91 (got {manual:.2f})")

# ── Output 2: Sector Table ───────────────────────────────────────────────────
def check_sector(name, n, mean_ts, std_dev, tol=0.05):
    row = sector_sum[sector_sum['sector']==name]
    if len(row) == 0:
        check(False, f"Sector '{name}' found in data")
        return
    row = row.iloc[0]
    check(int(row['company_count']) == n,
          f"'{name}' n={n} (actual {int(row['company_count'])})")
    check(abs(row['mean_score'] - mean_ts) < tol,
          f"'{name}' mean={mean_ts} (actual {row['mean_score']:.2f})")
    check(abs(row['std_dev'] - std_dev) < 0.05,
          f"'{name}' std={std_dev} (actual {row['std_dev']:.2f})")

check_sector("Electricity, Gas, Steam and AC Supply", 31, 53.67, 11.49)
check_sector("Coke and Refined Petroleum", 9, 52.32, 11.13)
check_sector("Motor Vehicles", 37, 51.76, 9.98)
check_sector("Insurance and Pension Funding", 20, 51.52, 10.12)
check_sector("Pharmaceuticals", 65, 51.18, 10.06)
check_sector("Basic Metals", 60, 50.80, 10.87)
check_sector("Non-Metallic Mineral Products", 40, 50.36, 8.69)
check_sector("Computer Programming and IT Services", 49, 50.24, 12.25)
check_sector("Chemicals Manufacturing", 101, 49.56, 9.32)
check_sector("Machinery and Equipment", 36, 49.46, 10.06)
check_sector("Rubber and Plastics", 36, 49.22, 9.90)
check_sector("Financial Services (excl. Insurance)", 94, 48.17, 9.88)

# ── Output 3: Pharmaceuticals Intra-Sector ───────────────────────────────────
def check_pharma(name, ts, c, sp, cl, sdg):
    row = scores[scores['company_name']==name]
    if len(row) == 0:
        check(False, f"Company '{name}' found in scores")
        return
    r = row.iloc[0]
    check(abs(r['transparency_score'] - ts) < 0.02, f"'{name}' TS={ts}")
    check(abs(r['completeness_pct'] - c) < 0.1, f"'{name}' C={c}")
    check(abs(r['specificity_pct'] - sp) < 0.1, f"'{name}' Sp={sp}")
    check(abs(r['clarity_pct'] - cl) < 0.1, f"'{name}' Cl={cl}")
    check(abs(r['sdg_alignment_pct'] - sdg) < 0.1, f"'{name}' SDG={sdg}")

check_pharma("Dabur India Limited",           73.72, 73.13, 57.38, 95.08, 82.35)
check_pharma("Lupin Limited",                 69.63, 68.68, 47.30, 98.65, 82.35)
check_pharma("Dr. Reddy's Laboratories Limited", 67.76, 73.42, 43.55, 85.48, 82.35)
check_pharma("Ipca Laboratories Limited",     66.26, 85.62, 28.36, 91.04, 52.94)
check_pharma("Syncom Formulations (India) Limited", 35.67, 36.33, 11.43, 88.57, 0.0)
check_pharma("Jagsonpal Pharmaceuticals Limited",   33.27, 30.84,  9.30, 90.70, 0.0)
check_pharma("Kopran Limited",                      32.38, 32.92, 23.68, 60.53, 0.0)

# Spread
check(abs(73.72 - 32.38 - 41.34) < 0.02, "Spread 73.72 - 32.38 = 41.34")

print(f"\n{'='*50}")
print(f"Total checks: {errors} failures" if errors else "All checks PASSED.")
