import pandas as pd
scores = pd.read_csv('data/analysis/transparency_scores.csv')
benchmarks = pd.read_csv('data/analysis/sector_benchmarks.csv')

# Machinery and Equipment - use this for intra-sector to connect with company example
mach = benchmarks[benchmarks['sector']=='Machinery and Equipment'].sort_values('transparency_score', ascending=False)
mach_s = mach.merge(scores[['company_name','completeness_pct','specificity_pct','clarity_pct','sdg_alignment_pct']], on='company_name', how='left')
print('Machinery and Equipment (n=' + str(len(mach_s)) + '):')
print('Top 6:')
for _, r in mach_s.head(6).iterrows():
    name = str(r['company_name'])[:50]
    ts = r['transparency_score']
    c = r['completeness_pct']
    sp = r['specificity_pct']
    cl = r['clarity_pct']
    sdg = r['sdg_alignment_pct']
    pct = r['percentile_rank']
    print('  TS=' + str(ts) + '  C=' + str(c) + ' Sp=' + str(sp) + ' Cl=' + str(cl) + ' SDG=' + str(sdg) + '  pct=' + str(pct) + '  ' + name)

print('Bottom 6:')
for _, r in mach_s.tail(6).iterrows():
    name = str(r['company_name'])[:50]
    ts = r['transparency_score']
    c = r['completeness_pct']
    sp = r['specificity_pct']
    cl = r['clarity_pct']
    sdg = r['sdg_alignment_pct']
    pct = r['percentile_rank']
    print('  TS=' + str(ts) + '  C=' + str(c) + ' Sp=' + str(sp) + ' Cl=' + str(cl) + ' SDG=' + str(sdg) + '  pct=' + str(pct) + '  ' + name)

print()
# Pharmaceuticals top 6 + bottom 5 with components
pharma = benchmarks[benchmarks['sector']=='Pharmaceuticals'].sort_values('transparency_score', ascending=False)
pharma_s = pharma.merge(scores[['company_name','completeness_pct','specificity_pct','clarity_pct','sdg_alignment_pct']], on='company_name', how='left')
print('Pharmaceuticals (n=' + str(len(pharma_s)) + ') top 6 + bottom 5 with components:')
print('Top 6:')
for _, r in pharma_s.head(6).iterrows():
    name = str(r['company_name'])[:50]
    ts = r['transparency_score']
    c = r['completeness_pct']
    sp = r['specificity_pct']
    cl = r['clarity_pct']
    sdg = r['sdg_alignment_pct']
    pct = r['percentile_rank']
    print('  TS=' + str(ts) + '  C=' + str(c) + ' Sp=' + str(sp) + ' Cl=' + str(cl) + ' SDG=' + str(sdg) + '  pct=' + str(pct) + '  ' + name)
print('Bottom 5:')
for _, r in pharma_s.tail(5).iterrows():
    name = str(r['company_name'])[:50]
    ts = r['transparency_score']
    c = r['completeness_pct']
    sp = r['specificity_pct']
    cl = r['clarity_pct']
    sdg = r['sdg_alignment_pct']
    pct = r['percentile_rank']
    print('  TS=' + str(ts) + '  C=' + str(c) + ' Sp=' + str(sp) + ' Cl=' + str(cl) + ' SDG=' + str(sdg) + '  pct=' + str(pct) + '  ' + name)
