"""Read-only research workspaces, linked by CIN and report ID.

The saved exports are the paper's score snapshot. Never rescore the corpus on
an HTTP request: attach reporting periods from the database and explicitly label
the snapshot. Detailed metric evidence always comes from the selected filing.
"""
from __future__ import annotations

import csv
import math
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func

from analysis.audit_checks.assurance import get_assurance_profile
from analysis.audit_checks.assurance_gap import check_assurance_gap
from analysis.audit_checks.consistency import run_all_consistency_checks
from analysis.audit_checks.greenwashing import find_claim_evidence_signals
from analysis.audit_checks.silent_removal import find_silently_removed_metrics
from analysis.compliance.sector_classification import get_sector_from_nic_code as classify_sector
from analysis.core.queries import to_number
from analysis.scoring.completeness_score import get_completeness_score, get_concept_universe
from analysis.scoring.sdg_alignment import get_sdg_alignment_score
from analysis.vagueness.vagueness_lexicon import analyze_vagueness
from api.converters import assurance_to_schema, consistency_to_schema, silent_removal_to_schema
from db.models import Company, Fact, Filing
from db.session import DEFAULT_DB_PATH, get_session

router = APIRouter()
DATA = Path(__file__).resolve().parents[2] / "data" / "analysis"
COMPONENTS = ("completeness_pct", "specificity_pct", "clarity_pct", "sdg_alignment_pct")
WEIGHTS = (0.4, 0.3, 0.2, 0.1)
METRICS = {
    "TotalScope1Emissions": "Scope 1 emissions",
    "TotalScope2Emissions": "Scope 2 emissions",
    "TotalScope3Emissions": "Scope 3 emissions",
    "TotalWasteGenerated": "Waste generated",
    "TotalVolumeOfWaterWithdrawal": "Water withdrawal",
    "TotalEnergyConsumedFromRenewableAndNonRenewableSources": "Total energy consumed",
}


def _csv(name):
    path = DATA / name
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _score(row):
    return {key: float(row[key]) for key in (*COMPONENTS, "transparency_score")}


def _stamp(path):
    return path.stat().st_mtime_ns if path.exists() else 0


@lru_cache(maxsize=1)
def _universe(signature):
    with get_session() as session:
        return get_concept_universe(session)


@lru_cache(maxsize=1)
def _snapshot(signature):
    scores = {r["cin"]: r for r in _csv("transparency_scores.csv")}
    benchmarks = {r["cin"]: r for r in _csv("sector_benchmarks.csv")}
    with get_session() as session:
        companies = session.query(Company).order_by(Company.name).all()
        filings = session.query(Filing).order_by(Filing.financial_year_end.desc(), Filing.id.desc()).all()
        latest = {}
        by_id = {}
        for filing in filings:
            by_id[filing.id] = filing
            latest.setdefault(filing.company_id, filing)
        rows = []
        for company in companies:
            filing = latest.get(company.id)
            score = scores.get(company.cin)
            benchmark = benchmarks.get(company.cin, {})
            rows.append({
                "id": company.id, "cin": company.cin, "name": company.name,
                "nic_code": company.nic_code,
                "sector": benchmark.get("sector") or classify_sector(company.nic_code),
                "filing_id": filing.id if filing else None,
                "financial_year_end": filing.financial_year_end if filing else None,
                "raw_fact_count": filing.raw_fact_count if filing else 0,
                "report_count": sum(f.company_id == company.id for f in filings),
                "score_source": "saved_latest_snapshot" if score else "not_scored",
                **(_score(score) if score else {k: None for k in (*COMPONENTS, "transparency_score")}),
            })
        companies_by_cin = {c.cin: c for c in companies}
        history = []
        for row in _csv("year_wise_scores.csv"):
            company = companies_by_cin.get(row["cin"])
            filing = by_id.get(int(row["filing_id"]))
            # An export must link to the same company's actual report.
            if company is None or filing is None or filing.company_id != company.id:
                continue
            history.append({
                "id": company.id, "cin": company.cin, "name": company.name,
                "sector": benchmarks.get(company.cin, {}).get("sector") or classify_sector(company.nic_code),
                "filing_id": filing.id, "financial_year_end": filing.financial_year_end,
                "financial_year": row["financial_year"], **_score(row),
            })
        fact_count = session.query(func.count(Fact.id)).scalar()
    return {
        "companies": rows, "history": history,
        "report_count": len(filings), "fact_count": fact_count,
        "score_updated_at": datetime.fromtimestamp(
            (DATA / "transparency_scores.csv").stat().st_mtime, timezone.utc
        ).isoformat() if scores else None,
        "methodology": "Saved research scores; latest report per CIN, with report periods reconstructed from the database. SDG breadth is a principle-to-goal coverage proxy. Scores describe disclosure, not environmental performance.",
    }


@router.get("/analytics/overview")
def overview():
    paths = [DATA / f for f in ("transparency_scores.csv", "sector_benchmarks.csv", "year_wise_scores.csv")]
    # Counts also invalidate cached metadata for non-SQLite deployments.
    with get_session() as session:
        counts = (session.query(func.count(Company.id)).scalar(), session.query(func.count(Filing.id)).scalar())
    return _snapshot(tuple(_stamp(p) for p in [*paths, DEFAULT_DB_PATH]) + counts)


def _fact(fact):
    return {"id": fact.id, "concept": fact.concept, "value": fact.value,
            "unit": fact.unit, "period_start": fact.period_start,
            "period_end": fact.period_end or fact.period_instant,
            "dimensions": fact.dimensions}


def metric_series(facts, concept):
    """Keep each unit and dimensional boundary separate; never sum duplicates."""
    import json
    groups = {}
    for fact in facts:
        if fact.concept != concept:
            continue
        value = to_number(fact.value)
        period = fact.period_end or fact.period_instant
        if value is None or not math.isfinite(value) or not period:
            continue
        key = (fact.unit, json.dumps(fact.dimensions or {}, sort_keys=True))
        groups.setdefault(key, {}).setdefault(period, []).append(fact)
    result = []
    for (unit, dimensions), periods in groups.items():
        points = []
        conflicts = []
        for period, records in sorted(periods.items()):
            values = {to_number(r.value) for r in records}
            if len(values) != 1:
                conflicts.append(period)
                continue
            points.append({"period": period, "value": next(iter(values)), "fact_ids": [r.id for r in records]})
        previous = points[-2]["value"] if len(points) > 1 else None
        latest = points[-1]["value"] if points else None
        change = round((latest - previous) / abs(previous) * 100, 2) if previous not in (None, 0) else None
        result.append({"concept": concept, "label": METRICS.get(concept, concept), "unit": unit,
                       "dimensions": json.loads(dimensions), "series": points,
                       "yoy_change_pct": change, "conflicting_periods": conflicts})
    return result


@router.get("/companies/{name}/workspace")
def workspace(name: str, filing_id: int | None = Query(default=None)):
    snapshot = overview()
    with get_session() as session:
        # Full names and CINs are exact identifiers here. Avoid ambiguous partial matches.
        company = session.query(Company).filter((Company.cin == name) | (func.lower(Company.name) == name.lower())).first()
        if company is None:
            raise HTTPException(404, "Company not found")
        filings = session.query(Filing).filter_by(company_id=company.id).order_by(Filing.financial_year_end.desc()).all()
        filing = next((f for f in filings if f.id == filing_id), None) if filing_id is not None else next(iter(filings), None)
        if filing is None:
            raise HTTPException(404, "Report not found for this company")
        facts = session.query(Fact).filter_by(filing_id=filing.id).order_by(Fact.id).all()
        row = next((r for r in snapshot["history"] if r["cin"] == company.cin and r["filing_id"] == filing.id), None)
        if row is None and filing.id == filings[0].id:
            row = next((r for r in snapshot["companies"] if r["cin"] == company.cin), None)
        score = {k: row[k] for k in (*COMPONENTS, "transparency_score")} if row and row["transparency_score"] is not None else None
        universe = _universe(_stamp(DEFAULT_DB_PATH))
        score_source = "saved_research_snapshot" if score else "not_in_score_export"
        scoring_error = None
        if score is None:
            # New uploads can be scored without changing the frozen paper exports.
            from analysis.scoring.transparency_score import get_transparency_score
            try:
                result = get_transparency_score(session, filing.id, concept_universe=universe)
                score = {"completeness_pct": result.completeness.completeness_pct,
                         "specificity_pct": result.specificity_clarity.specificity_pct,
                         "clarity_pct": result.specificity_clarity.clarity_pct,
                         "sdg_alignment_pct": result.sdg.sdg_alignment_pct,
                         "transparency_score": result.composite_score}
                score_source = "computed_current_rules"
            except (ImportError, OSError):
                scoring_error = "The scoring model is unavailable. Filed evidence and rule-based checks remain available."
        completeness = get_completeness_score(session, filing.id, universe)
        sdg = get_sdg_alignment_score(session, filing.id)
        narratives = {}
        for fact in facts:
            if "ExplanatoryTextBlock" in fact.concept and len(fact.value.strip()) >= 30:
                narratives.setdefault((fact.concept, fact.value.strip()), fact)
        lexical = []
        for fact in narratives.values():
            analysis = analyze_vagueness(fact.value)
            if analysis.is_flagged_vague or analysis.is_evasion:
                lexical.append(_fact(fact))
        signals = []
        for signal in find_claim_evidence_signals(session, filing.id):
            sources = [_fact(f) for f in facts if f.concept == signal.narrative_source_concept and signal.matched_sentence in f.value]
            signals.append({
                "concept": signal.concept, "severity": signal.severity.value,
                "matched_sentence": signal.matched_sentence, "rationale": signal.rationale,
                "assurance_level": signal.assurance_level, "sources": sources,
                "numeric_evidence": [_fact(f) for f in facts if f.concept == signal.concept],
            })
        gaps = []
        seen_gaps = set()
        assurance_profile = get_assurance_profile(session, filing.id)
        for fact in narratives.values():
            for gap in check_assurance_gap(session, filing.id, fact.value, assurance_profile=assurance_profile, facts=facts):
                key = (gap.concept, gap.claim_sentence, gap.severity.value)
                if key in seen_gaps:
                    continue
                seen_gaps.add(key)
                gaps.append({"concept": gap.concept, "rationale": gap.explanation,
                             "severity": gap.severity.value, "source": _fact(fact)})
        return {
            "company": {"id": company.id, "name": company.name, "cin": company.cin,
                        "sector": classify_sector(company.nic_code), "nic_code": company.nic_code},
            "filing": {"id": filing.id, "financial_year_start": filing.financial_year_start,
                       "financial_year_end": filing.financial_year_end, "raw_fact_count": filing.raw_fact_count,
                       "source_url": filing.xbrl_source_url},
            "filings": [{"id": f.id, "financial_year_end": f.financial_year_end} for f in filings],
            "score": score, "score_source": score_source, "scoring_error": scoring_error,
            "score_evidence": {"accepted_concepts": completeness.filed_concept_count,
                "universe_size": completeness.universe_size, "narrative_segments": len(narratives),
                "kpi_segments": sum(analyze_vagueness(f.value).has_kpi for f in narratives.values()),
                "sdgs_covered": sorted(sdg.sdgs_covered), "principles_disclosed": sorted(sdg.principles_disclosed)},
            "metrics": [series for concept in METRICS for series in metric_series(facts, concept)],
            "signals": signals, "lexical_flags": lexical, "assurance_gaps": gaps,
            "silent_removals": [silent_removal_to_schema(r) for r in find_silently_removed_metrics(session, filing.id)],
            "assurance": assurance_to_schema(assurance_profile),
            "consistency": consistency_to_schema(run_all_consistency_checks(session, filing.id)),
            "facts": [_fact(f) for f in facts],
        }
