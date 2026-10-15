"""
Synthetic positive/negative test cases for the greenwashing signal
detector — built as controlled fixtures rather than relying on finding a
real company with a contradiction, since NIIT (our only ingested company
so far) genuinely has none. These tests prove the detector actually fires
under a known contradiction and stays silent when it shouldn't, which the
NIIT-only tests couldn't demonstrate on their own.

Uses a dedicated synthetic company (CIN starting "TESTSYN") so it never
collides with real ingested data, and tears itself down after each test.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from analysis.audit_checks.greenwashing import Severity, find_claim_evidence_signals
from db.models import Company, Fact, Filing
from db.session import get_session, init_db

TEST_CIN = "TESTSYN000000000001"


@pytest.fixture
def synthetic_filing():
    """Creates a synthetic company + filing, yields the filing_id, then
    deletes everything belonging to this test CIN afterward."""
    init_db()
    with get_session() as session:
        company = Company(cin=TEST_CIN, name="Synthetic Test Co")
        session.add(company)
        session.flush()

        filing = Filing(
            company_id=company.id,
            financial_year_start="2025-04-01",
            financial_year_end="2026-03-31",
            xbrl_source_url="synthetic://test",
            raw_fact_count=0,
        )
        session.add(filing)
        session.flush()
        filing_id = filing.id

    yield filing_id

    with get_session() as session:
        company = session.query(Company).filter_by(cin=TEST_CIN).one_or_none()
        if company:
            session.delete(company)  # cascades to filings and facts


def _add_numeric_facts(session, filing_id, concept, previous_value, current_value):
    session.add_all([
        Fact(filing_id=filing_id, concept=concept, value=str(previous_value), unit="MtCO2e",
             period_start="2024-04-01", period_end="2025-03-31", dimensions={}),
        Fact(filing_id=filing_id, concept=concept, value=str(current_value), unit="MtCO2e",
             period_start="2025-04-01", period_end="2026-03-31", dimensions={}),
    ])


def _add_narrative_fact(session, filing_id, text, concept="SomeExplanatoryTextBlock"):
    session.add(Fact(
        filing_id=filing_id, concept=concept, value=text, unit=None,
        period_start="2025-04-01", period_end="2026-03-31", dimensions={},
    ))


def test_genuine_contradiction_is_detected():
    """POSITIVE CASE: narrative explicitly claims a Scope 1 reduction, but
    the filed numbers show Scope 1 increased 50%. This is the exact shape
    of contradiction the module exists to catch."""
    init_db()
    with get_session() as session:
        company = Company(cin=TEST_CIN, name="Synthetic Test Co")
        session.add(company)
        session.flush()
        filing = Filing(
            company_id=company.id, financial_year_start="2025-04-01",
            financial_year_end="2026-03-31", xbrl_source_url="synthetic://test", raw_fact_count=0,
        )
        session.add(filing)
        session.flush()
        filing_id = filing.id

        _add_numeric_facts(session, filing_id, "TotalScope1Emissions", previous_value=100, current_value=150)
        _add_narrative_fact(
            session, filing_id,
            "We successfully reduced our Scope 1 emissions by 20% this year through efficiency measures.",
        )

    try:
        with get_session() as session:
            signals = find_claim_evidence_signals(session, filing_id)

            assert len(signals) == 1, f"Expected exactly 1 signal, got {len(signals)}"
            signal = signals[0]
            assert signal.concept == "TotalScope1Emissions"
            assert signal.trend.direction == "increased"
            assert signal.trend.yoy_change_pct == 50.0
            assert "scope 1" in signal.matched_sentence.lower()
            # No assurance tag exists for this synthetic concept -> unassured -> NOTABLE
            assert signal.severity == Severity.NOTABLE
    finally:
        with get_session() as session:
            c = session.query(Company).filter_by(cin=TEST_CIN).one_or_none()
            if c:
                session.delete(c)


def test_honest_disclosure_of_increase_produces_no_signal():
    """NEGATIVE CASE: narrative honestly states the metric increased — no
    improvement claim at all — so no contradiction exists to flag. This
    mirrors the real NIIT case (Scope 1 'are increase', no improvement
    language) that originally motivated this fix."""
    init_db()
    with get_session() as session:
        company = Company(cin=TEST_CIN, name="Synthetic Test Co")
        session.add(company)
        session.flush()
        filing = Filing(
            company_id=company.id, financial_year_start="2025-04-01",
            financial_year_end="2026-03-31", xbrl_source_url="synthetic://test", raw_fact_count=0,
        )
        session.add(filing)
        session.flush()
        filing_id = filing.id

        _add_numeric_facts(session, filing_id, "TotalScope1Emissions", previous_value=100, current_value=150)
        _add_narrative_fact(session, filing_id, "Scope 1 emissions increased compared to last year due to higher operational activity.")

    try:
        with get_session() as session:
            signals = find_claim_evidence_signals(session, filing_id)
            assert len(signals) == 0, f"Expected no signals for honest disclosure, got {len(signals)}"
    finally:
        with get_session() as session:
            c = session.query(Company).filter_by(cin=TEST_CIN).one_or_none()
            if c:
                session.delete(c)


def test_claim_matching_a_decreasing_metric_produces_no_signal():
    """NEGATIVE CASE: narrative claims a reduction, and the numbers agree
    (genuinely decreased) — no contradiction, so no signal."""
    init_db()
    with get_session() as session:
        company = Company(cin=TEST_CIN, name="Synthetic Test Co")
        session.add(company)
        session.flush()
        filing = Filing(
            company_id=company.id, financial_year_start="2025-04-01",
            financial_year_end="2026-03-31", xbrl_source_url="synthetic://test", raw_fact_count=0,
        )
        session.add(filing)
        session.flush()
        filing_id = filing.id

        _add_numeric_facts(session, filing_id, "TotalScope1Emissions", previous_value=150, current_value=100)
        _add_narrative_fact(session, filing_id, "We reduced Scope 1 emissions by 33% this year.")

    try:
        with get_session() as session:
            signals = find_claim_evidence_signals(session, filing_id)
            assert len(signals) == 0, f"Expected no signals when claim matches reality, got {len(signals)}"
    finally:
        with get_session() as session:
            c = session.query(Company).filter_by(cin=TEST_CIN).one_or_none()
            if c:
                session.delete(c)


def test_duplicate_identical_paragraph_produces_one_signal_not_many():
    """Reproduces the real NIIT dedup bug: the same paragraph filed
    multiple times (once per NGRBC Principle in real filings) must
    collapse to one signal, with the occurrence count preserved."""
    init_db()
    with get_session() as session:
        company = Company(cin=TEST_CIN, name="Synthetic Test Co")
        session.add(company)
        session.flush()
        filing = Filing(
            company_id=company.id, financial_year_start="2025-04-01",
            financial_year_end="2026-03-31", xbrl_source_url="synthetic://test", raw_fact_count=0,
        )
        session.add(filing)
        session.flush()
        filing_id = filing.id

        _add_numeric_facts(session, filing_id, "TotalScope1Emissions", previous_value=100, current_value=150)
        text = "We reduced Scope 1 emissions by 20% this year."
        for principle_num in range(1, 4):  # simulate 3 repeated filings of the same text
            _add_narrative_fact(session, filing_id, text, concept=f"SomeExplanatoryTextBlockP{principle_num}")

    try:
        with get_session() as session:
            signals = find_claim_evidence_signals(session, filing_id)
            assert len(signals) == 1, f"Expected 1 deduplicated signal, got {len(signals)}"
            assert signals[0].matched_in_n_locations == 3
    finally:
        with get_session() as session:
            c = session.query(Company).filter_by(cin=TEST_CIN).one_or_none()
            if c:
                session.delete(c)