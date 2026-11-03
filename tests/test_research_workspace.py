"""Regression checks for report linkage and like-for-like evidence series."""
import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from db.models import Base, Company, Filing, Fact
from api.analytics import metric_series, overview, workspace
from analysis.core.trends import get_trend
from analysis.audit_checks.assurance_gap import check_assurance_gap


def fact(value, period, unit="tCO2e", dimensions=None, fact_id=1):
    return Fact(id=fact_id, filing_id=1, concept="TotalScope1Emissions", value=str(value), unit=unit,
                period_end=period, dimensions=dimensions or {})


def test_metric_series_separates_units_boundaries_and_conflicting_duplicates():
    facts = [fact(10,"2025-03-31"),fact(12,"2026-03-31",fact_id=2),
             fact(12,"2026-03-31",fact_id=3),
             fact(30,"2026-03-31",unit="kg",fact_id=4),
             fact(100,"2026-03-31",dimensions={"Boundary":"Subsidiary"},fact_id=5)]
    series = metric_series(facts,"TotalScope1Emissions")
    assert len(series) == 3
    aggregate = next(s for s in series if s["unit"] == "tCO2e" and not s["dimensions"])
    assert aggregate["yoy_change_pct"] == 20
    assert aggregate["series"][-1]["fact_ids"] == [2,3]
    facts.append(fact(99,"2026-03-31",fact_id=6))
    conflicted = next(s for s in metric_series(facts,"TotalScope1Emissions") if s["unit"] == "tCO2e" and not s["dimensions"])
    assert conflicted["conflicting_periods"] == ["2026-03-31"]
    assert conflicted["yoy_change_pct"] is None


def test_zero_baseline_is_not_an_infinite_percentage():
    s = metric_series([fact(0,"2025-03-31"),fact(12,"2026-03-31",fact_id=2)],"TotalScope1Emissions")[0]
    assert s["series"][0]["value"] == 0
    assert s["yoy_change_pct"] is None


def test_screening_trend_does_not_compare_different_units_or_duplicate_periods():
    engine=create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(Company(id=1,cin="TEST",name="Test entity"))
        session.add(Filing(id=1,company_id=1,financial_year_start="2025-04-01",financial_year_end="2026-03-31",xbrl_source_url="synthetic://test"))
        session.add_all([fact(10,"2025-03-31"),fact(12,"2026-03-31",fact_id=2),fact(12,"2026-03-31",fact_id=3)])
        session.flush()
        assert get_trend(session,1,"TotalScope1Emissions").yoy_change_pct == 20
        session.add(fact(2,"2026-03-31",unit="kg",fact_id=4));session.flush()
        assert get_trend(session,1,"TotalScope1Emissions").yoy_change_pct is None


def test_assurance_gap_accepts_a_disclosed_zero_as_evidence():
    from analysis.audit_checks.assurance import AssuranceProfile
    signals=check_assurance_gap(None,1,"We reduced our scope 1 emissions by ten percent.",
        assurance_profile=AssuranceProfile(items=[]),facts=[fact(0,"2026-03-31")])
    assert signals
    assert all(signal.fact_found for signal in signals)
    assert all(not signal.severity.value.startswith("high") for signal in signals)


def test_assurance_gap_does_not_confuse_an_intensity_tag_with_an_absolute_fact():
    from analysis.audit_checks.assurance import AssuranceProfile
    unrelated=fact(123,"2026-03-31")
    unrelated.concept="TotalScope1EmissionsIntensity"
    signals=check_assurance_gap(None,1,"We reduced our scope 1 emissions by ten percent.",
        assurance_profile=AssuranceProfile(items=[]),facts=[unrelated])
    assert signals and not signals[0].fact_found


def test_api_rejects_unknown_company_and_wrong_report_link():
    from fastapi.testclient import TestClient
    from api.main import app
    with TestClient(app) as client:
        assert client.get("/companies/NO_SUCH_COMPANY_987654321/workspace").status_code == 404
        assert client.get("/companies/Triveni%20Turbine%20Limited/workspace?filing_id=1207").status_code == 404
        assert client.get("/companies/Triveni%20Turbine%20Limited/workspace?filing_id=invalid").status_code == 422
        response=client.post("/companies/upload-and-analyze",files={"file":("report.pdf",b"test","application/pdf")})
        assert response.status_code == 422


@pytest.mark.skipif(not (Path(__file__).resolve().parents[1] / "data/analysis/transparency_scores.csv").exists(), reason="Requires the local research corpus")
def test_saved_snapshot_matches_paper_and_report_ids():
    data=overview()
    assert len([r for r in data["companies"] if r["transparency_score"] is not None]) == 1164
    assert data["report_count"] >= 1172
    assert len(data["history"]) == 16
    financial=[r for r in data["companies"] if r["sector"] == "Financial Services (excl. Insurance)" and r["transparency_score"] is not None]
    assert len(financial) == 94
    assert round(sum(r["transparency_score"] for r in financial)/len(financial),2) == 48.17
    report=workspace("Triveni Turbine Limited",None)
    assert report["filing"]["id"] == 197
    assert report["score"]["transparency_score"] == 68.91
    assert report["score_evidence"]["accepted_concepts"] == 613
    assert report["score_evidence"]["narrative_segments"] == 52
    # Current lexical rules do not reproduce the frozen export. Surface this
    # difference instead of presenting inferred snapshot counts as live evidence.
    assert report["score_evidence"]["kpi_segments"] == 26
    assert len(report["score_evidence"]["sdgs_covered"]) == 12
