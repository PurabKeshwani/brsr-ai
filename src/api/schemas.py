"""
Pydantic response models — the API's public contract. Nothing in the
`db` or `analysis` modules is ever returned directly; every response is
explicitly shaped here, so internal refactors (renaming a dataclass field,
changing a concept string) never silently change the API's shape.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class CompanySummary(BaseModel):
    id: int
    cin: str
    name: str
    nic_code: Optional[str] = None


class FilingSummary(BaseModel):
    id: int
    financial_year_start: str
    financial_year_end: str
    raw_fact_count: int


class TrendPoint(BaseModel):
    period: str
    value: float


class MetricTrend(BaseModel):
    concept: str
    series: list[TrendPoint]
    latest_value: Optional[float]
    previous_value: Optional[float]
    yoy_change_pct: Optional[float]
    direction: str


class ConsistencyCheckItem(BaseModel):
    concept: str
    context: str
    status: str
    message: str


class ConsistencySummary(BaseModel):
    total_checks: int
    passed: int
    failed: int
    skipped: int
    failures: list[ConsistencyCheckItem]


class AssuranceSummary(BaseModel):
    total_disclosure_areas: int
    assured_count: int
    reasonable_count: int
    limited_count: int
    unassured_count: int
    reasonable_assurance_pct: float
    low_assurance_areas: list[str]


class GreenwashingSignalItem(BaseModel):
    concept: str
    severity: str
    matched_sentence: str
    previous_value: Optional[float]
    latest_value: Optional[float]
    yoy_change_pct: Optional[float]
    assurance_level: Optional[str]
    rationale: str


class SilentRemovalItem(BaseModel):
    concept: str
    context: str
    prior_year_value: str
    prior_year_period: str
    rationale: str


class CompanyFullReport(BaseModel):
    company: CompanySummary
    filing: FilingSummary
    key_trends: list[MetricTrend]
    consistency: ConsistencySummary
    assurance: AssuranceSummary
    greenwashing_signals: list[GreenwashingSignalItem]
    silent_removals: list[SilentRemovalItem]


class IngestRequest(BaseModel):
    company_hint: str
    xbrl_url: str


class IngestResponse(BaseModel):
    filing_id: int
    company_id: int
    company_name: str
    financial_year_start: str
    financial_year_end: str
    fact_count: int

class TransparencyScoreBreakdown(BaseModel):
    completeness_pct: float
    specificity_pct: float
    clarity_pct: float
    sdg_alignment_pct: float
    composite_score: float


class TruthAuditorSummary(BaseModel):
    total_narrative_segments_checked: int
    claim_evidence_contradictions_count: int
    silent_removals_count: int
    vague_segments_count: int
    has_high_confidence_contradiction: bool
    claim_evidence_details: list[GreenwashingSignalItem]
    silent_removal_details: list[SilentRemovalItem]


class SectorBenchmarkInfo(BaseModel):
    sector: str
    company_transparency_score: float
    sector_mean: float
    sector_median: float
    percentile_rank: float
    sector_peer_count: int
    is_sector_leader: bool
    is_sector_laggard: bool
    benchmark_reliable: bool