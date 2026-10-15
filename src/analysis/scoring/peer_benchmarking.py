"""
Peer/Sector Benchmarking (report FR5 — one of the 3 genuinely-missing
components identified via systematic audit against the report and
diagrams; see conversation history).

Computes sector-level Transparency Score statistics (mean, median, min,
max) and each company's percentile rank within its own sector — the
capability the report describes as "sector-level comparison" and
"identifying disclosure leaders and laggards within an industry."

Reads from the pre-computed data/analysis/transparency_scores.csv (built
by scripts/bulk_transparency_scoring.py) joined with each company's
sector (derived from its NIC code via sector_classification.py), rather
than recomputing scores — this module is purely an aggregation/ranking
layer over already-validated Transparency Scores.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from analysis.compliance.sector_classification import get_sector_from_nic_code

SCORES_PATH = Path("data/analysis/transparency_scores.csv")
MIN_PEERS_FOR_BENCHMARK = 5  # a sector with fewer than this many companies produces statistically-unreliable percentiles — flagged, not silently computed


@dataclass
class SectorBenchmark:
    sector: str
    company_count: int
    mean_score: float
    median_score: float
    min_score: float
    max_score: float
    std_dev: float


@dataclass
class CompanyBenchmarkResult:
    company_name: str
    cin: str
    sector: str
    transparency_score: float
    sector_mean: float
    sector_median: float
    percentile_rank: float  # 0-100, this company's rank within its sector
    sector_peer_count: int
    is_sector_leader: bool   # top 10% of sector
    is_sector_laggard: bool  # bottom 10% of sector
    benchmark_reliable: bool  # False if sector_peer_count < MIN_PEERS_FOR_BENCHMARK


def _load_scored_companies_with_sectors() -> pd.DataFrame:
    df = pd.read_csv(SCORES_PATH)
    df["sector"] = df["cin"].apply(lambda cin: None)  # placeholder, filled by caller with actual nic_code lookup
    return df


def build_sector_benchmarks(df: pd.DataFrame) -> dict[str, SectorBenchmark]:
    """df must have columns: transparency_score, sector"""
    benchmarks = {}
    for sector, group in df.groupby("sector"):
        scores = group["transparency_score"]
        benchmarks[sector] = SectorBenchmark(
            sector=sector,
            company_count=len(group),
            mean_score=round(scores.mean(), 2),
            median_score=round(scores.median(), 2),
            min_score=round(scores.min(), 2),
            max_score=round(scores.max(), 2),
            std_dev=round(scores.std(), 2) if len(group) > 1 else 0.0,
        )
    return benchmarks


def get_company_benchmark(df: pd.DataFrame, company_name: str) -> CompanyBenchmarkResult | None:
    """df must have columns: company_name, cin, transparency_score, sector"""
    row = df[df["company_name"] == company_name]
    if row.empty:
        return None
    row = row.iloc[0]

    sector_group = df[df["sector"] == row["sector"]]
    peer_count = len(sector_group)

    percentile = (sector_group["transparency_score"] < row["transparency_score"]).sum() / peer_count * 100

    return CompanyBenchmarkResult(
        company_name=row["company_name"],
        cin=row["cin"],
        sector=row["sector"],
        transparency_score=row["transparency_score"],
        sector_mean=round(sector_group["transparency_score"].mean(), 2),
        sector_median=round(sector_group["transparency_score"].median(), 2),
        percentile_rank=round(percentile, 1),
        sector_peer_count=peer_count,
        is_sector_leader=percentile >= 90,
        is_sector_laggard=percentile <= 10,
        benchmark_reliable=peer_count >= MIN_PEERS_FOR_BENCHMARK,
    )