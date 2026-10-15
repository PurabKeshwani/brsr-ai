import pandas as pd
s = pd.read_csv('data/analysis/sector_summary.csv')
r = s[s['reliable'] == True].copy()
top12c = r.sort_values('company_count', ascending=False).head(12)
top12c_sorted = top12c.sort_values('mean_score', ascending=False)
for _, row in top12c_sorted.iterrows():
    print(f"{row['sector']} & {row['company_count']} & {row['mean_score']:.2f} & {row['std_dev']:.2f} \\\\ \hline")
