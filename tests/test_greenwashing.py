import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from analysis.audit_checks.greenwashing import find_claim_evidence_signals
from analysis.core.queries import get_company_by_name, get_latest_filing
from analysis.audit_checks.silent_removal import find_silently_removed_metrics
from db.session import get_session, init_db


def _get_niit_filing():
    init_db()
    session_ctx = get_session()
    session = session_ctx.__enter__()
    company = get_company_by_name(session, "NIIT Learning")
    assert company is not None, "Run scripts/ingest_company.py for NIIT first"
    filing = get_latest_filing(session, company.id)
    return session, filing


def test_claim_evidence_signals_run_without_crashing_and_are_explainable():
    session, filing = _get_niit_filing()
    signals = find_claim_evidence_signals(session, filing.id)

    for s in signals:
        assert s.matched_sentence.strip() != ""
        assert s.trend.latest_value is not None
        assert s.trend.previous_value is not None
        assert s.rationale != ""
        print(f"\n[{s.severity.value}] {s.concept}  (source paragraph appeared {s.matched_in_n_locations}x)")
        print(f"  Matched sentence: {s.matched_sentence}")
        print(f"  Trend: {s.trend.previous_value} -> {s.trend.latest_value} ({s.trend.yoy_change_pct}%)")
        print(f"  Assurance: {s.assurance_level or 'none'}")

    print(f"\nTotal signals found: {len(signals)}")


def test_silent_removal_check_runs_without_crashing():
    session, filing = _get_niit_filing()
    flags = find_silently_removed_metrics(session, filing.id)

    for f in flags[:10]:  # print a sample for manual review, don't assert a specific count
        print(f"\nSilently removed: {f.concept}")
        print(f"  Prior value: {f.prior_year_value} (period {f.prior_year_period})")
        print(f"  Context: {f.dimensions_key}")