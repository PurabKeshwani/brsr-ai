"""
Synthetic positive/negative test cases for the silent-removal detector —
mirrors the rigor applied to greenwashing_synthetic.py, since
silent_removal.py had only a "doesn't crash" test until now, never a
"detects the right thing" test.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from db.models import Company, Fact, Filing
from db.session import get_session, init_db
from analysis.silent_removal import find_silently_removed_metrics

TEST_CIN = "TESTSYN000000000002"

PRIOR_PERIOD = "2025-03-31"
CURRENT_PERIOD = "2026-03-31"


def _make_filing(session):
    company = Company(cin=TEST_CIN, name="Synthetic Test Co 2")
    session.add(company)
    session.flush()
    filing = Filing(
        company_id=company.id, financial_year_start="2025-04-01",
        financial_year_end="2026-03-31", xbrl_source_url="synthetic://test", raw_fact_count=0,
    )
    session.add(filing)
    session.flush()
    return filing.id


def _add_fact(session, filing_id, concept, value, period_end):
    session.add(Fact(
        filing_id=filing_id, concept=concept, value=value, unit="pure",
        period_start=None, period_end=period_end, dimensions={},
    ))


def _cleanup():
    with get_session() as session:
        c = session.query(Company).filter_by(cin=TEST_CIN).one_or_none()
        if c:
            session.delete(c)


def test_metric_present_in_prior_but_missing_in_current_is_flagged():
    init_db()
    with get_session() as session:
        filing_id = _make_filing(session)
        # Establishes that both periods exist in this filing:
        _add_fact(session, filing_id, "AlwaysPresent", "1", PRIOR_PERIOD)
        _add_fact(session, filing_id, "AlwaysPresent", "1", CURRENT_PERIOD)
        # The metric under test — present prior, absent current:
        _add_fact(session, filing_id, "RemovedMetric", "500", PRIOR_PERIOD)

    try:
        with get_session() as session:
            flags = find_silently_removed_metrics(session, filing_id)
            flagged_concepts = {f.concept for f in flags}
            assert "RemovedMetric" in flagged_concepts
            removed_flag = next(f for f in flags if f.concept == "RemovedMetric")
            assert removed_flag.prior_year_value == "500"
            assert removed_flag.prior_year_period == PRIOR_PERIOD
    finally:
        _cleanup()


def test_metric_present_in_both_periods_is_not_flagged():
    init_db()
    with get_session() as session:
        filing_id = _make_filing(session)
        _add_fact(session, filing_id, "StableMetric", "10", PRIOR_PERIOD)
        _add_fact(session, filing_id, "StableMetric", "12", CURRENT_PERIOD)

    try:
        with get_session() as session:
            flags = find_silently_removed_metrics(session, filing_id)
            flagged_concepts = {f.concept for f in flags}
            assert "StableMetric" not in flagged_concepts
    finally:
        _cleanup()


def test_metric_only_in_current_period_is_not_flagged():
    """A newly-added disclosure (present only in the current period, never
    filed before) is not a 'removal' — must not be flagged."""
    init_db()
    with get_session() as session:
        filing_id = _make_filing(session)
        _add_fact(session, filing_id, "AlwaysPresent", "1", PRIOR_PERIOD)
        _add_fact(session, filing_id, "AlwaysPresent", "1", CURRENT_PERIOD)
        _add_fact(session, filing_id, "NewMetric", "42", CURRENT_PERIOD)

    try:
        with get_session() as session:
            flags = find_silently_removed_metrics(session, filing_id)
            flagged_concepts = {f.concept for f in flags}
            assert "NewMetric" not in flagged_concepts
    finally:
        _cleanup()


def test_zero_or_na_prior_value_is_not_flagged():
    """A prior value of '0' or 'NA' isn't meaningful data — its absence
    this year isn't a concerning removal, per the module's own stated
    design (see silent_removal.py's skip condition)."""
    init_db()
    with get_session() as session:
        filing_id = _make_filing(session)
        _add_fact(session, filing_id, "AlwaysPresent", "1", PRIOR_PERIOD)
        _add_fact(session, filing_id, "AlwaysPresent", "1", CURRENT_PERIOD)
        _add_fact(session, filing_id, "ZeroPriorMetric", "0", PRIOR_PERIOD)
        _add_fact(session, filing_id, "NAPriorMetric", "NA", PRIOR_PERIOD)

    try:
        with get_session() as session:
            flags = find_silently_removed_metrics(session, filing_id)
            flagged_concepts = {f.concept for f in flags}
            assert "ZeroPriorMetric" not in flagged_concepts
            assert "NAPriorMetric" not in flagged_concepts
    finally:
        _cleanup()


def test_single_period_filing_returns_no_flags():
    """If the entire filing only has one distinct period (no prior-year
    comparative data present at all), there's nothing to compare against
    — must return an empty list, not crash or guess."""
    init_db()
    with get_session() as session:
        filing_id = _make_filing(session)
        _add_fact(session, filing_id, "OnlyMetric", "99", CURRENT_PERIOD)

    try:
        with get_session() as session:
            flags = find_silently_removed_metrics(session, filing_id)
            assert flags == []
    finally:
        _cleanup()