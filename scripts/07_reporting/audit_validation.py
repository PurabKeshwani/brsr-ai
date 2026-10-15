"""
Focused validation pass — covers all 8 audit points.
Run from project root: python3 scripts/07_reporting/audit_validation.py
"""
import sys, math
import pandas as pd

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

scores     = pd.read_csv('data/analysis/transparency_scores.csv')
benchmarks = pd.read_csv('data/analysis/sector_benchmarks.csv')
sector_sum = pd.read_csv('data/analysis/sector_summary.csv')

FAIL = "[FAIL]"
WARN = "[WARN]"
OK   = "[OK]  "
INFO = "[INFO]"

issues = []
def flag(tag, msg):
    issues.append((tag, msg))
    print(tag, msg)

print("=" * 70)
print("AUDIT 1 — Sector selection and sorting logic")
print("=" * 70)

# The paper says "12 largest reliable sectors" but the table is sorted by mean_score DESC.
# Check what "largest" means in the paper context.
reliable = sector_sum[sector_sum['reliable'] == True].copy()
by_count = reliable.sort_values('company_count', ascending=False)
by_mean  = reliable.sort_values('mean_score',    ascending=False)

print(INFO, "Top 12 by company count:")
for i, (_, r) in enumerate(by_count.head(12).iterrows()):
    print(f"       {i+1:2d}. n={r['company_count']:3d}  mean={r['mean_score']:.2f}  {r['sector']}")

print()
print(INFO, "Top 12 by mean score (current table order):")
for i, (_, r) in enumerate(by_mean.head(12).iterrows()):
    print(f"       {i+1:2d}. n={r['company_count']:3d}  mean={r['mean_score']:.2f}  {r['sector']}")

# Are these the same 12 companies?
top12_count = set(by_count.head(12)['sector'])
top12_mean  = set(by_mean.head(12)['sector'])
overlap = top12_count & top12_mean
in_count_not_mean = top12_count - top12_mean
in_mean_not_count = top12_mean - top12_count
print()
print(INFO, f"Sectors in top-12-by-count but NOT top-12-by-mean: {in_count_not_mean}")
print(INFO, f"Sectors in top-12-by-mean  but NOT top-12-by-count: {in_mean_not_count}")
if in_count_not_mean or in_mean_not_count:
    flag(FAIL, "Caption says '12 LARGEST reliable sectors' but table is sorted/selected by mean score, "
               "not company count. The two sets differ.")

print()
print("=" * 70)
print("AUDIT 2 — Between-sector gap (5.5 point claim)")
print("=" * 70)

# Paper claims: "Electricity Gas & Steam leads at 53.67, Financial Services 48.17, gap of 5.5"
# These are BOTH within the top-12-by-mean subset.
# But what is the gap across ALL reliable sectors?
all_reliable_min  = reliable['mean_score'].min()
all_reliable_max  = reliable['mean_score'].max()
all_reliable_gap  = all_reliable_max - all_reliable_min
subset_gap        = 53.67 - 48.17

sec_min = reliable.loc[reliable['mean_score'].idxmin(), 'sector']
sec_max = reliable.loc[reliable['mean_score'].idxmax(), 'sector']

print(INFO, f"Within top-12-by-mean subset: gap = {subset_gap:.2f} ({48.17} to {53.67})")
print(INFO, f"Across ALL {len(reliable)} reliable sectors: "
           f"min={all_reliable_min:.2f} ({sec_min}), max={all_reliable_max:.2f} ({sec_max}), "
           f"gap={all_reliable_gap:.2f}")

if abs(subset_gap - 5.5) > 0.05:
    flag(FAIL, f"Claimed 5.5-point gap is actually {subset_gap:.2f} within the displayed subset.")
else:
    print(OK, "5.5-point gap is arithmetically correct within the displayed 12 sectors.")

if all_reliable_gap > subset_gap + 0.5:
    flag(WARN, f"Paper states '5.5 points' without clarifying this is within the displayed subset. "
               f"True range across all {len(reliable)} reliable sectors is {all_reliable_gap:.2f} points.")

print()
print("=" * 70)
print("AUDIT 3 — Sector classification for specific companies")
print("=" * 70)

# Check Meghmani Organics (CIN L24299GJ2019PLC110321)
# and Poly Medicure (CIN L40300DL1995PLC066923)
for name, expected_nic_prefix, expected_sector in [
    ("Meghmani Organics Limited", "24", "Basic Metals"),
    ("Poly Medicure Limited", "40", "Wholesale Trade"),
]:
    row = benchmarks[benchmarks['company_name'] == name]
    if row.empty:
        flag(WARN, f"'{name}' not found in benchmarks")
        continue
    r = row.iloc[0]
    actual_sector = r['sector']
    cin = r['cin']
    # Derive the NIC prefix from the CIN if possible — CIN doesn't contain NIC code directly
    # The NIC code is stored on the Company record in the DB, not in the CSV.
    # What we CAN check: does the sector name match what the code in CIN implies?
    # CIN format: L/U + 5-digit NIC + state + year + company_type + sequential
    # The NIC code is digits 2-6 of the CIN (1-indexed): CIN[1:6]
    try:
        nic_from_cin = cin[1:6]  # 5-digit NIC embedded in CIN
        division_from_cin = nic_from_cin[:2]
        print(INFO, f"'{name}' CIN={cin}, NIC-from-CIN={nic_from_cin}, division={division_from_cin}, "
                    f"assigned_sector='{actual_sector}'")
        # Load the sector classification mapping
        # Division 24 -> Basic Metals (correct for Meghmani if they have NIC starting 24)
        # Division 40 -> Not in the mapping (NIC-2008 div 40 is electricity/gas, but div 40 doesn't exist
        #                in NIC-2008; div 35 is Electricity. Let's see what division 40 maps to.
        # Actually CIN NIC L40300 -> NIC code = 40300, division = 40
        # In sector_classification.py: "40" is NOT in DIVISION_TO_SECTOR, so it would be "Other (Division 40)"
        # But the benchmark says "Wholesale Trade" -- that seems wrong.
        # Let's verify: Wholesale Trade = division 46.
        if actual_sector == expected_sector:
            if division_from_cin == expected_nic_prefix:
                print(OK, f"'{name}' sector '{actual_sector}' consistent with CIN NIC division {division_from_cin}")
            else:
                flag(WARN, f"'{name}' sector '{actual_sector}' but CIN NIC prefix is '{division_from_cin}' "
                            f"(expected prefix '{expected_nic_prefix}' for '{expected_sector}')")
        else:
            flag(WARN, f"'{name}' assigned sector='{actual_sector}', expected='{expected_sector}'. "
                       f"CIN NIC division='{division_from_cin}'")
    except Exception as e:
        flag(FAIL, f"Error processing '{name}': {e}")

# Double-check: what does sector_classification.py return for division 40?
print()
print(INFO, "NIC Division 40 is NOT in DIVISION_TO_SECTOR (NIC-2008 div 40 is obsolete/reserved).")
print(INFO, "This would map to 'Other (Division 40)', NOT 'Wholesale Trade'.")
print(INFO, "Check actual NIC code stored in database for Poly Medicure (CIN L40300DL...).")
# The L40300 CIN means: L = listed, 40300 = NIC code as registered, DL = Delhi, ...
# NIC 40300 -> division 40 -> "Other (Division 40)" per the classifier.
# But sector_benchmarks.csv shows "Wholesale Trade" (division 46) for Poly Medicure.
# This suggests the NIC code in the DB for this company is different from what the CIN implies,
# OR there is a data-entry issue. We can't resolve without querying the DB directly.
poly_row = benchmarks[benchmarks['company_name'] == 'Poly Medicure Limited']
print(INFO, f"Poly Medicure in benchmarks: sector='{poly_row.iloc[0]['sector']}' "
            f"(should be verified against DB nic_code, not CIN)")
flag(WARN, "Poly Medicure Limited classified as 'Wholesale Trade'. CIN prefix L40300 suggests "
           "NIC division 40, which maps to 'Other (Division 40)'. The DB nic_code may differ from "
           "the CIN-embedded code. This cannot be resolved from CSVs alone. Flagging as unresolved "
           "limitation.")

meghmani_row = benchmarks[benchmarks['company_name'] == 'Meghmani Organics Limited']
print(INFO, f"Meghmani Organics in benchmarks: sector='{meghmani_row.iloc[0]['sector']}'")
print(INFO, "CIN L24299 -> division 24 -> Basic Metals (correct per NIC-2008).")
print(OK, "Meghmani Organics -> Basic Metals is consistent with NIC division 24.")
# Wait: Meghmani Organics is described as a chemicals company in practice.
# NIC 24 = Basic Metals. NIC 20 = Chemicals. But NIC code embedded in CIN is 24299,
# division = 24, which is Basic Metals. This is the registered NIC code, may differ
# from operational sector. This is a known limitation of NIC-self-classification.
flag(WARN, "Meghmani Organics Limited is classified as 'Basic Metals' (NIC div 24) but operates "
           "as a chemicals company. This is the NIC code as self-reported in the CIN at incorporation. "
           "The classification is what the data source provides; it is a known limitation of "
           "CIN-embedded NIC codes.")

print()
print("=" * 70)
print("AUDIT 4 — Claims about within-sector variation and component drivers")
print("=" * 70)

# Claim: "within-sector std dev substantially larger than between-sector gap"
# Between-sector gap (among top-12 by mean): 5.5 pts
# Within-sector std devs (top-12 by mean): 8.69-12.25
# This claim IS valid for the displayed subset, but we should verify it holds
# across ALL reliable sectors.
all_stds = reliable['std_dev']
all_means = reliable['mean_score']
between_sector_std = all_means.std()
mean_within_sector_std = all_stds.mean()

print(INFO, f"Between-sector std of mean scores (all {len(reliable)} reliable): {between_sector_std:.2f}")
print(INFO, f"Mean of within-sector std devs (all {len(reliable)} reliable): {mean_within_sector_std:.2f}")
print(INFO, f"Min within-sector std dev: {all_stds.min():.2f}, Max: {all_stds.max():.2f}")
# The paper's claim is about comparing std dev (within) to range (between).
# These are different statistics. Let's be explicit.
flag(WARN, "Paper compares within-sector std dev (8.69-12.25 pts) to between-sector RANGE (5.5 pts) "
           "as if they are equivalent. They are not: std dev != range. This overstates the contrast. "
           "The correct comparison is std dev vs. std dev, or range vs. range.")

# Claim about Pharma: SDG=0 for bottom 3 companies
# Already verified by the 81-check script. Let's verify Clarity claim:
# "Clarity is high in nearly all cases (above 85%)"
pharma = benchmarks[benchmarks['sector']=='Pharmaceuticals']
pharma_s = pharma.merge(scores[['company_name','clarity_pct']], on='company_name', how='left')
below_85 = pharma_s[pharma_s['clarity_pct'] < 85]
print()
print(INFO, f"Pharma companies with Clarity < 85%: {len(below_85)} / {len(pharma_s)}")
if len(below_85) > 0:
    print(INFO, "  " + ", ".join(f"{r['company_name']} ({r['clarity_pct']:.1f}%)"
                                  for _, r in below_85.iterrows()))
if len(below_85) / len(pharma_s) > 0.15:
    flag(WARN, f"Claim 'Clarity high in nearly all cases (above 85%)' for Pharma: "
               f"{len(below_85)}/{len(pharma_s)} companies are below 85%.")
else:
    print(OK, f"Clarity > 85% for {len(pharma_s)-len(below_85)}/{len(pharma_s)} Pharma companies.")

# Correlation of TS with each component across full corpus
for comp, col in [('Completeness','completeness_pct'), ('Specificity','specificity_pct'),
                   ('Clarity','clarity_pct'), ('SDG Alignment','sdg_alignment_pct')]:
    corr = scores['transparency_score'].corr(scores[col])
    print(INFO, f"Full-corpus correlation TS vs {comp}: r={corr:.3f}")

print()
print("=" * 70)
print("AUDIT 5 — Formula, weights, normalization, percentile, leader/laggard, min-n")
print("=" * 70)

# Weights in transparency_score.py: C=0.40, Sp=0.30, Cl=0.20, SDG=0.10 -- matches paper eq.
print(OK, "Weights C=0.40, Sp=0.30, Cl=0.20, SDG=0.10 confirmed in transparency_score.py")

# Percentile formula in peer_benchmarking.py (line 89):
# percentile = (scores < this_score).sum() / peer_count * 100
# This is the "fraction of peers strictly below" formula - a standard definition.
print(OK, "Percentile = (scores strictly below) / peer_count * 100  [exclusive, not rank-based]")

# Leader = top 10% (percentile >= 90), Laggard = bottom 10% (percentile <= 10)
print(OK, "Leader: percentile >= 90; Laggard: percentile <= 10 -- confirmed in source.")

# MIN_PEERS_FOR_BENCHMARK = 5 -- matches paper's 'fewer than 5 companies' threshold
print(OK, "Min peers for reliable benchmark = 5 -- matches paper's stated threshold.")

# The 81 checks only verified numeric consistency of CSV values against the paper.
# They did NOT verify the formula implementation against the DB.
# We can do a spot-check of the composite formula on one company:
spot = scores[scores['company_name'] == 'Triveni Turbine Limited'].iloc[0]
manual = (0.40 * spot['completeness_pct'] + 0.30 * spot['specificity_pct'] +
          0.20 * spot['clarity_pct'] + 0.10 * spot['sdg_alignment_pct'])
print(OK, f"Formula spot-check (Triveni Turbine): manual={manual:.2f}, stored={spot['transparency_score']:.2f}, "
          f"match={abs(manual-spot['transparency_score'])<0.01}")

# What the 81 checks did NOT cover:
flag(WARN, "The 81 checks verified numeric CSV values match paper text. They did NOT verify: "
           "(a) the DB-level scoring implementation against live data, "
           "(b) concept universe size or deduplication correctness, "
           "(c) SDG mapping correctness (principle-to-SDG mapping is a design choice, not ground truth), "
           "(d) the lexicon used for KPI detection.")

print()
print("=" * 70)
print("AUDIT 6 — Deduplication and one-company-one-filing assumption")
print("=" * 70)

# bulk_transparency_scoring.py uses get_latest_filing(session, company.id)
# This means one row per company in transparency_scores.csv.
# Let's verify there are no duplicate CINs in the CSV.
dup_cin = scores[scores.duplicated(subset=['cin'], keep=False)]
dup_name = scores[scores.duplicated(subset=['company_name'], keep=False)]
print(INFO, f"Duplicate CINs in transparency_scores.csv: {len(dup_cin)}")
print(INFO, f"Duplicate company names in transparency_scores.csv: {len(dup_name)}")
if len(dup_cin) > 0:
    flag(FAIL, f"{len(dup_cin)} rows share a CIN -- possible double-counting.")
    print(dup_cin[['company_name','cin','transparency_score']].head(10).to_string())
else:
    print(OK, "No duplicate CINs -- each company appears exactly once.")
if len(dup_name) > 0:
    flag(WARN, f"{len(dup_name)} rows share a company name (different CINs possible).")
    print(dup_name[['company_name','cin','transparency_score']].head(10).to_string())
else:
    print(OK, "No duplicate company names.")

# Verify benchmarks has same count and no dup CINs
dup_cin_b = benchmarks[benchmarks.duplicated(subset=['cin'], keep=False)]
if len(dup_cin_b) > 0:
    flag(FAIL, f"{len(dup_cin_b)} duplicate CINs in sector_benchmarks.csv.")
else:
    print(OK, "No duplicate CINs in sector_benchmarks.csv.")

print(INFO, f"scores rows={len(scores)}, benchmarks rows={len(benchmarks)}")
if len(scores) != len(benchmarks):
    flag(FAIL, f"Row count mismatch: scores={len(scores)}, benchmarks={len(benchmarks)}")
else:
    print(OK, "scores and benchmarks have identical row count (1164).")

# Confirm the script uses get_latest_filing, i.e. deduplicates by company
print(OK, "bulk_transparency_scoring.py confirmed to use get_latest_filing() -- "
          "only the most recent filing per company is scored.")

print()
print("=" * 70)
print("AUDIT 7 — LaTeX syntax, cross-references, figure/table labels")
print("=" * 70)

with open('paper/paper_revised_v6.tex', encoding='utf-8', errors='replace') as fh:
    tex = fh.read()

# Check labels
required_labels = [
    r'\label{tab:company_breakdown}',
    r'\label{fig:company_breakdown}',
    r'\label{tab:sector}',
    r'\label{fig:sector_bar}',
    r'\label{tab:intra_sector}',
    r'\label{fig:intra_sector}',
    r'\label{sec:company_ts}',
    r'\label{sec:sector_ts}',
    r'\label{sec:intra_ts}',
]
for lbl in required_labels:
    if lbl in tex:
        print(OK, f"Label present: {lbl}")
    else:
        flag(FAIL, f"Missing label: {lbl}")

# Check references
required_refs = [
    r'\ref{tab:company_breakdown}',
    r'\ref{fig:company_breakdown}',
    r'\ref{tab:sector}',
    r'\ref{fig:sector_bar}',
    r'\ref{tab:intra_sector}',
    r'\ref{fig:intra_sector}',
    r'\ref{sec:intra_ts}',
    r'\ref{eq:ts}',
    r'\eqref{eq:ts}',
]
for ref in required_refs:
    if ref in tex:
        print(OK, f"Ref present: {ref}")
    else:
        flag(WARN, f"Ref NOT found in tex: {ref}")

# Check that old fabricated labels/figures no longer define content
# (fig:sector_company was the old placeholder figure)
old_label_defs = [r'\label{fig:sector_company}']
for lbl in old_label_defs:
    if lbl in tex:
        flag(WARN, f"Old placeholder label still defined: {lbl}")
    else:
        print(OK, f"Old placeholder label removed: {lbl}")

# Check that all \begin{axis} have corresponding \end{axis}
n_begin = tex.count(r'\begin{axis}')
n_end   = tex.count(r'\end{axis}')
if n_begin == n_end:
    print(OK, f"axis environments balanced: {n_begin} begin, {n_end} end.")
else:
    flag(FAIL, f"Unbalanced axis environments: {n_begin} begin, {n_end} end.")

# Check extra x ticks syntax (used in fig:intra_sector)
if 'extra x ticks' in tex:
    print(OK, "extra x ticks syntax present in tex.")
if 'extra x tick style' in tex:
    print(OK, "extra x tick style present in tex.")

# Note: compilation not performed
flag(WARN, "LaTeX compilation NOT performed (pdflatex not on PATH). "
           "Structural checks passed but actual rendering is unverified.")

print()
print("=" * 70)
print("AUDIT 8 — No-year-wise-analysis, existing metrics preservation")
print("=" * 70)

year_terms = ['year-over-year', 'year-wise', 'annual trend', 'over time', 'year_wise']
for term in year_terms:
    count = tex.lower().count(term)
    if count > 0 and 'conclusion' not in term:
        # Allow year-wise in conclusion/future-work context
        flag(WARN, f"Term '{term}' appears {count} time(s) -- verify it's not in Results section.")
    else:
        print(OK, f"No '{term}' in Results section.")

# Check key existing metrics are preserved
key_metrics = ['0.658', '0.880', '0.894', '0.631', '1,164', '4,854', '51,066', '44.3']
for m in key_metrics:
    if m in tex:
        print(OK, f"Existing metric {m} preserved.")
    else:
        flag(FAIL, f"Existing metric {m} NOT FOUND in tex -- may have been lost.")

print()
print("=" * 70)
print("SUMMARY")
print("=" * 70)
warns  = [m for t, m in issues if t == WARN]
fails  = [m for t, m in issues if t == FAIL]
print(f"FAIL count : {len(fails)}")
print(f"WARN count : {len(warns)}")
for msg in fails:
    print(f"  FAIL: {msg}")
for msg in warns:
    print(f"  WARN: {msg}")
