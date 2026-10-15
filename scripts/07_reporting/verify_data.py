import pandas as pd

scores = pd.read_csv('data/analysis/transparency_scores.csv')
benchmarks = pd.read_csv('data/analysis/sector_benchmarks.csv')
sector_sum = pd.read_csv('data/analysis/sector_summary.csv')

# Verify the formula for Triveni Turbine
co = scores[scores['company_name'] == 'Triveni Turbine Limited'].iloc[0]
bench_co = benchmarks[benchmarks['company_name'] == 'Triveni Turbine Limited'].iloc[0]
manual_ts = 0.40 * co['completeness_pct'] + 0.30 * co['specificity_pct'] + 0.20 * co['clarity_pct'] + 0.10 * co['sdg_alignment_pct']
print('Triveni Turbine Limited:')
print('  Completeness:', co['completeness_pct'])
print('  Specificity:', co['specificity_pct'])
print('  Clarity:', co['clarity_pct'])
print('  SDG Alignment:', co['sdg_alignment_pct'])
print('  TS (stored):', co['transparency_score'])
print('  TS (manual):', round(manual_ts, 2))
print('  Sector:', bench_co['sector'])
print('  Sector mean:', bench_co['sector_mean'])
print('  Sector median:', bench_co['sector_median'])
print('  Sector peers:', bench_co['sector_peer_count'])
print('  Percentile:', bench_co['percentile_rank'])
print('  Segments:', co['total_narrative_segments'])
print()

rel = sector_sum[sector_sum['reliable']==True].sort_values('mean_score', ascending=False)
print('Top 15 sectors by mean TS (reliable only):')
for i, (_, r) in enumerate(rel.head(15).iterrows()):
    sector = r['sector']
    n = r['company_count']
    mn = r['mean_score']
    med = r['median_score']
    lo = r['min_score']
    hi = r['max_score']
    print(f'  {i+1:2d}. {sector:<45} n={n:3d} mean={mn:.2f} median={med:.2f} range=[{lo:.1f},{hi:.1f}]')

print()
print('Bottom 10 reliable sectors:')
for _, r in rel.tail(10).iterrows():
    print(f'  {r["sector"]:<40}  n={r["company_count"]:3d}  mean={r["mean_score"]:.2f}')

print()
print('Pharmaceuticals sector top 8 + bottom 5:')
pharma = benchmarks[benchmarks['sector']=='Pharmaceuticals'].sort_values('transparency_score', ascending=False)
pharma_s = pharma.merge(scores[['company_name','completeness_pct','specificity_pct','clarity_pct','sdg_alignment_pct']], on='company_name', how='left')
print('Top 8:')
for _, r in pharma_s.head(8).iterrows():
    print(f'  {r["transparency_score"]:5.2f}  {str(r["company_name"])[:50]:<50}  pct={r["percentile_rank"]}')
print('Bottom 5:')
for _, r in pharma_s.tail(5).iterrows():
    print(f'  {r["transparency_score"]:5.2f}  {str(r["company_name"])[:50]:<50}  pct={r["percentile_rank"]}')

print()
print('Chemicals Manufacturing top 10 + bottom 5 with components:')
chem = benchmarks[benchmarks['sector']=='Chemicals Manufacturing'].sort_values('transparency_score', ascending=False)
chem_s = chem.merge(scores[['company_name','completeness_pct','specificity_pct','clarity_pct','sdg_alignment_pct']], on='company_name', how='left')
print('Top 10:')
for _, r in chem_s.head(10).iterrows():
    print(f'  {r["transparency_score"]:5.2f}  C={r["completeness_pct"]:5.1f} Sp={r["specificity_pct"]:5.1f} Cl={r["clarity_pct"]:5.1f} SDG={r["sdg_alignment_pct"]:5.1f}  {str(r["company_name"])[:45]}')
print('Bottom 5:')
for _, r in chem_s.tail(5).iterrows():
    print(f'  {r["transparency_score"]:5.2f}  C={r["completeness_pct"]:5.1f} Sp={r["specificity_pct"]:5.1f} Cl={r["clarity_pct"]:5.1f} SDG={r["sdg_alignment_pct"]:5.1f}  {str(r["company_name"])[:45]}')
