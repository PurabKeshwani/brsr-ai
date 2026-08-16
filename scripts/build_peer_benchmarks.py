"""
Builds sector-benchmarked Transparency Score data for all companies —
joins transparency_scores.csv with each company's NIC-derived sector,
computes sector-level statistics, and writes a company-level output CSV
with percentile rank, leader/laggard flags, per the report's stated peer-
benchmarking capability (FR5).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd

from analysis.peer_benchmarking import (
    MIN_PEERS_FOR_BENCHMARK,
    build_sector_benchmarks,
    get_company_benchmark,
)
from analysis.sector_classification import get_sector_from_nic_code
from db.models import Company
from db.session import get_session, init_db

SCORES_PATH = Path("data/analysis/transparency_scores.csv")
OUTPUT_PATH = Path("data/analysis/sector_benchmarks.csv")
SECTOR_SUMMARY_PATH = Path("data/analysis/sector_summary.csv")


def main():
    scores_df = pd.read_csv(SCORES_PATH)
    print(f"Loaded {len(scores_df)} scored companies")

    init_db()
    with get_session() as session:
        cin_to_nic = {c.cin: c.nic_code for c in session.query(Company).all()}

    scores_df["sector"] = scores_df["cin"].map(cin_to_nic).apply(get_sector_from_nic_code)

    print(f"\nSector distribution:")
    sector_counts = scores_df["sector"].value_counts()
    print(sector_counts.head(20))

    sector_benchmarks = build_sector_benchmarks(scores_df)

    reliable_sectors = sum(1 for b in sector_benchmarks.values() if b.company_count >= MIN_PEERS_FOR_BENCHMARK)
    print(f"\n{len(sector_benchmarks)} distinct sectors, {reliable_sectors} with >= {MIN_PEERS_FOR_BENCHMARK} companies (reliable benchmark)")

    company_results = []
    for _, row in scores_df.iterrows():
        result = get_company_benchmark(scores_df, row["company_name"])
        if result:
            company_results.append({
                "company_name": result.company_name,
                "cin": result.cin,
                "sector": result.sector,
                "transparency_score": result.transparency_score,
                "sector_mean": result.sector_mean,
                "sector_median": result.sector_median,
                "percentile_rank": result.percentile_rank,
                "sector_peer_count": result.sector_peer_count,
                "is_sector_leader": result.is_sector_leader,
                "is_sector_laggard": result.is_sector_laggard,
                "benchmark_reliable": result.benchmark_reliable,
            })

    company_df = pd.DataFrame(company_results)
    company_df.to_csv(OUTPUT_PATH, index=False)
    print(f"\nWritten company-level benchmarks to {OUTPUT_PATH}")

    sector_summary_rows = [
        {"sector": b.sector, "company_count": b.company_count, "mean_score": b.mean_score,
         "median_score": b.median_score, "min_score": b.min_score, "max_score": b.max_score,
         "std_dev": b.std_dev, "reliable": b.company_count >= MIN_PEERS_FOR_BENCHMARK}
        for b in sorted(sector_benchmarks.values(), key=lambda b: -b.company_count)
    ]
    pd.DataFrame(sector_summary_rows).to_csv(SECTOR_SUMMARY_PATH, index=False)
    print(f"Written sector summary to {SECTOR_SUMMARY_PATH}")

    print("\n=== Top 10 sectors by company count, with score stats ===")
    for row in sector_summary_rows[:10]:
        reliability = "✓" if row["reliable"] else "⚠ small-n"
        print(f"  {row['sector']:<40} n={row['company_count']:<4} mean={row['mean_score']:<6} "
              f"median={row['median_score']:<6} range=[{row['min_score']}-{row['max_score']}] {reliability}")

    print("\n=== Example: sector leaders and laggards (largest sector) ===")
    largest_sector = sector_summary_rows[0]["sector"]
    sector_companies = company_df[company_df["sector"] == largest_sector].sort_values("transparency_score", ascending=False)
    print(f"Sector: {largest_sector}")
    print("Top 3:")
    for _, r in sector_companies.head(3).iterrows():
        print(f"  {r['transparency_score']:.1f}  {r['company_name']} (percentile={r['percentile_rank']})")
    print("Bottom 3:")
    for _, r in sector_companies.tail(3).iterrows():
        print(f"  {r['transparency_score']:.1f}  {r['company_name']} (percentile={r['percentile_rank']})")


if __name__ == "__main__":
    main()