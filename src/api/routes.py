"""
API route handlers. Every handler that touches the DB opens exactly one
session per request and translates internal exceptions (IngestionError)
into proper HTTP error responses — nothing internal ever leaks to the
client as a raw 500 with a stack trace.
"""
from __future__ import annotations

from fastapi import UploadFile, File
import shutil
import uuid
from ingestion.xbrl_ingest import ingest_filing

import pandas as pd
from pathlib import Path

from analysis.scoring.completeness_score import get_concept_universe
from analysis.scoring.transparency_score import get_transparency_score
from analysis.truth_auditor import run_truth_audit
from api.converters import transparency_score_to_schema, greenwashing_signal_to_schema, silent_removal_to_schema
from api.schemas import TransparencyScoreBreakdown, TruthAuditorSummary, SectorBenchmarkInfo

SECTOR_BENCHMARKS_PATH = Path("data/analysis/sector_benchmarks.csv")

from fastapi import APIRouter, HTTPException
from sqlalchemy.orm import Session

from analysis.audit_checks.assurance import get_assurance_profile
from analysis.audit_checks.consistency import run_all_consistency_checks
from analysis.audit_checks.greenwashing import find_claim_evidence_signals
from analysis.core.queries import get_all_filings, get_company_by_name, get_latest_filing
from analysis.audit_checks.silent_removal import find_silently_removed_metrics
from analysis.core.trends import get_trend
from api.converters import (
    assurance_to_schema,
    consistency_to_schema,
    greenwashing_signal_to_schema,
    silent_removal_to_schema,
    trend_to_schema,
)
from api.schemas import (
    CompanyFullReport,
    CompanySummary,
    FilingSummary,
    IngestRequest,
    IngestResponse,
)
from db.models import Company, Filing
from db.session import get_session
from ingestion.xbrl_ingest import IngestionError, ingest_company_by_url

router = APIRouter()

KEY_TRENDS = [
    "TotalScope1Emissions", "TotalScope2Emissions", "TotalScope3Emissions",
    "TotalWasteGenerated", "TotalVolumeOfWaterWithdrawal",
    "TotalEnergyConsumedFromRenewableAndNonRenewableSources",
]


def _company_to_schema(c: Company) -> CompanySummary:
    return CompanySummary(id=c.id, cin=c.cin, name=c.name, nic_code=c.nic_code)


def _filing_to_schema(f: Filing) -> FilingSummary:
    return FilingSummary(
        id=f.id, financial_year_start=f.financial_year_start,
        financial_year_end=f.financial_year_end, raw_fact_count=f.raw_fact_count,
    )


def _get_company_or_404(session: Session, name: str) -> Company:
    company = get_company_by_name(session, name)
    if company is None:
        raise HTTPException(status_code=404, detail=f"No company found matching '{name}'. Ingest it first via POST /companies/ingest")
    return company


def _get_latest_filing_or_404(session: Session, company: Company) -> Filing:
    filing = get_latest_filing(session, company.id)
    if filing is None:
        raise HTTPException(status_code=404, detail=f"Company '{company.name}' exists but has no ingested filings")
    return filing


@router.get("/companies", response_model=list[CompanySummary])
def list_companies():
    with get_session() as session:
        companies = session.query(Company).order_by(Company.name).all()
        return [_company_to_schema(c) for c in companies]


@router.get("/companies/{name}/filings", response_model=list[FilingSummary])
def list_filings(name: str):
    with get_session() as session:
        company = _get_company_or_404(session, name)
        filings = get_all_filings(session, company.id)
        return [_filing_to_schema(f) for f in filings]


@router.get("/companies/{name}/report", response_model=CompanyFullReport)
def get_company_report(name: str):
    """The primary endpoint — returns the complete analysis for a
    company's latest filing in one call, matching what
    scripts/run_full_analysis.py prints, but structured for a frontend."""
    with get_session() as session:
        company = _get_company_or_404(session, name)
        filing = _get_latest_filing_or_404(session, company)

        trends = [trend_to_schema(get_trend(session, filing.id, concept)) for concept in KEY_TRENDS]
        consistency = consistency_to_schema(run_all_consistency_checks(session, filing.id))
        assurance = assurance_to_schema(get_assurance_profile(session, filing.id))
        greenwashing = [greenwashing_signal_to_schema(s) for s in find_claim_evidence_signals(session, filing.id)]
        silent_removals = [silent_removal_to_schema(f) for f in find_silently_removed_metrics(session, filing.id)]

        return CompanyFullReport(
            company=_company_to_schema(company),
            filing=_filing_to_schema(filing),
            key_trends=trends,
            consistency=consistency,
            assurance=assurance,
            greenwashing_signals=greenwashing,
            silent_removals=silent_removals,
        )


@router.post("/companies/ingest", response_model=IngestResponse)
def ingest_company(req: IngestRequest):
    with get_session() as session:
        try:
            filing = ingest_company_by_url(session, req.xbrl_url, req.company_hint)
        except IngestionError as e:
            raise HTTPException(status_code=422, detail=str(e))

        return IngestResponse(
            filing_id=filing.id,
            company_id=filing.company_id,
            company_name=filing.company.name,
            financial_year_start=filing.financial_year_start,
            financial_year_end=filing.financial_year_end,
            fact_count=filing.raw_fact_count,
        )

@router.get("/companies/{name}/transparency-score", response_model=TransparencyScoreBreakdown)
def get_company_transparency_score(name: str):
    with get_session() as session:
        company = _get_company_or_404(session, name)
        filing = _get_latest_filing_or_404(session, company)

        universe = get_concept_universe(session)
        result = get_transparency_score(session, filing.id, concept_universe=universe)
        return transparency_score_to_schema(result)


@router.get("/companies/{name}/truth-audit", response_model=TruthAuditorSummary)
def get_company_truth_audit(name: str):
    with get_session() as session:
        company = _get_company_or_404(session, name)
        filing = _get_latest_filing_or_404(session, company)

        report = run_truth_audit(session, filing.id)
        return TruthAuditorSummary(
            total_narrative_segments_checked=report.total_narrative_segments_checked,
            claim_evidence_contradictions_count=len(report.claim_evidence_contradictions),
            silent_removals_count=len(report.silent_removals),
            vague_segments_count=len(report.vague_segments),
            has_high_confidence_contradiction=report.has_high_confidence_contradiction,
            claim_evidence_details=[greenwashing_signal_to_schema(s) for s in report.claim_evidence_contradictions],
            silent_removal_details=[silent_removal_to_schema(f) for f in report.silent_removals],
        )


@router.get("/companies/{name}/sector-benchmark", response_model=SectorBenchmarkInfo)
def get_company_sector_benchmark(name: str):
    if not SECTOR_BENCHMARKS_PATH.exists():
        raise HTTPException(status_code=503, detail="Sector benchmark data not yet generated. Run scripts/build_peer_benchmarks.py first.")

    df = pd.read_csv(SECTOR_BENCHMARKS_PATH)
    row = df[df["company_name"].str.lower() == name.lower()]
    if row.empty:
        # try partial match, consistent with other endpoints' company lookup behavior
        row = df[df["company_name"].str.lower().str.contains(name.lower())]
    if row.empty:
        raise HTTPException(status_code=404, detail=f"No sector benchmark found for company matching '{name}'")

    r = row.iloc[0]
    return SectorBenchmarkInfo(
        sector=r["sector"],
        company_transparency_score=float(r["transparency_score"]),
        sector_mean=float(r["sector_mean"]),
        sector_median=float(r["sector_median"]),
        percentile_rank=float(r["percentile_rank"]),
        sector_peer_count=int(r["sector_peer_count"]),
        is_sector_leader=bool(r["is_sector_leader"]),
        is_sector_laggard=bool(r["is_sector_laggard"]),
        benchmark_reliable=bool(r["benchmark_reliable"]),
    )

UPLOAD_DIR = Path("data/xbrl_uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/companies/upload-and-analyze", response_model=CompanyFullReport)
async def upload_and_analyze(file: UploadFile = File(...)):
    """
    Accepts an XBRL file upload (NOT PDF — see project design rationale:
    this system deliberately relies on SEBI-mandated, officially-tagged
    XBRL rather than PDF/OCR extraction, which was evaluated and rejected
    earlier in this project for unreliable accuracy). Ingests it
    immediately and returns the full analysis report, reusing the exact
    same computation path as the standard company-report endpoint.
    """
    if not file.filename.lower().endswith((".xml", ".xbrl")):
        raise HTTPException(
            status_code=422,
            detail="Only XBRL files (.xml or .xbrl) are supported. This system relies on "
                   "SEBI's officially-tagged XBRL format rather than PDF extraction, by design."
        )

    temp_path = UPLOAD_DIR / f"{uuid.uuid4().hex}_{file.filename}"
    try:
        with open(temp_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        with get_session() as session:
            try:
                filing = ingest_filing(session, temp_path, source_url=f"upload://{file.filename}")
            except IngestionError as e:
                raise HTTPException(status_code=422, detail=f"Could not process XBRL file: {e}")

            company = filing.company
            universe = get_concept_universe(session)

            trends = [trend_to_schema(get_trend(session, filing.id, concept)) for concept in KEY_TRENDS]
            consistency = consistency_to_schema(run_all_consistency_checks(session, filing.id))
            assurance = assurance_to_schema(get_assurance_profile(session, filing.id))
            greenwashing = [greenwashing_signal_to_schema(s) for s in find_claim_evidence_signals(session, filing.id)]
            silent_removals = [silent_removal_to_schema(f) for f in find_silently_removed_metrics(session, filing.id)]

            return CompanyFullReport(
                company=_company_to_schema(company),
                filing=_filing_to_schema(filing),
                key_trends=trends,
                consistency=consistency,
                assurance=assurance,
                greenwashing_signals=greenwashing,
                silent_removals=silent_removals,
            )
    finally:
        if temp_path.exists():
            temp_path.unlink()

@router.get("/companies/compare")
def compare_companies(names: str):
    """
    Peer-to-peer comparison. `names` is a comma-separated list of company
    names (partial match, same lookup as other endpoints), e.g.
    ?names=Mastek,NIIT Learning,Coal India. Returns each company's core
    comparable metrics side by side — reuses existing computation paths,
    no new analysis logic.
    """
    company_names = [n.strip() for n in names.split(",") if n.strip()]
    if len(company_names) < 2:
        raise HTTPException(status_code=422, detail="Provide at least 2 company names, comma-separated")
    if len(company_names) > 5:
        raise HTTPException(status_code=422, detail="Maximum 5 companies for comparison")

    results = []
    with get_session() as session:
        universe = get_concept_universe(session)

        for name in company_names:
            company = get_company_by_name(session, name)
            if company is None:
                results.append({"company_name": name, "error": "not found"})
                continue

            filing = _get_latest_filing_or_404(session, company)
            ts_result = get_transparency_score(session, filing.id, concept_universe=universe)
            audit = run_truth_audit(session, filing.id)

            trends = {}
            for concept in KEY_TRENDS:
                trend = get_trend(session, filing.id, concept)
                trends[concept] = {
                    "latest_value": trend.latest_value,
                    "yoy_change_pct": trend.yoy_change_pct,
                    "direction": trend.direction,
                }

            results.append({
                "company_name": company.name,
                "cin": company.cin,
                "transparency_score": ts_result.composite_score,
                "completeness_pct": ts_result.completeness.completeness_pct,
                "specificity_pct": ts_result.specificity_clarity.specificity_pct,
                "clarity_pct": ts_result.specificity_clarity.clarity_pct,
                "sdg_alignment_pct": ts_result.sdg.sdg_alignment_pct,
                "claim_evidence_contradictions": len(audit.claim_evidence_contradictions),
                "silent_removals": len(audit.silent_removals),
                "trends": trends,
            })

    return {"companies": results}