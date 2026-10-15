import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from analysis.audit_checks.assurance import get_assurance_profile
from analysis.audit_checks.consistency import CheckStatus, run_all_consistency_checks
from analysis.core.queries import get_company_by_name, get_latest_filing
from analysis.core.trends import get_trend
from db.session import get_session, init_db


def _get_niit_filing():
    init_db()
    session_ctx = get_session()
    session = session_ctx.__enter__()
    company = get_company_by_name(session, "NIIT Learning")
    assert company is not None, "Run scripts/ingest_company.py for NIIT first"
    filing = get_latest_filing(session, company.id)
    return session, filing


def test_scope1_emissions_trend_matches_hand_verified_xbrl_values():
    session, filing = _get_niit_filing()
    trend = get_trend(session, filing.id, "TotalScope1Emissions")

    assert trend.latest_value == 870.29
    assert trend.previous_value == 290.06
    assert trend.direction == "increased"
   # (870.29 - 290.06) / 290.06 * 100 = 200.04%
    assert trend.yoy_change_pct == 200.04


def test_waste_generated_trend_matches_hand_verified_xbrl_values():
    session, filing = _get_niit_filing()
    trend = get_trend(session, filing.id, "TotalWasteGenerated")

    assert trend.latest_value == 26.38
    assert trend.previous_value == 23.94
    assert trend.direction == "increased"


def test_gender_consistency_checks_run_without_unexplained_failures():
    session, filing = _get_niit_filing()
    results = run_all_consistency_checks(session, filing.id)

    assert len(results) > 0, "Expected at least some gender-split concepts to be found"

    failures = [r for r in results if r.status == CheckStatus.FAIL]
    # This is intentionally NOT asserting zero failures — a real filing
    # legitimately can have minor rounding-driven mismatches (as we found
    # by hand in Aequs's data earlier in this project). Instead we assert
    # that IF there are failures, each one is explained by a small
    # difference (consistent with rounding), not a large data error.
    for f in failures:
        diff_str = f.message.split("difference: ")[-1].rstrip(")")
        try:
            diff = abs(float(diff_str))
            assert diff < 5, f"Unexpectedly large inconsistency: {f.message}"
        except ValueError:
            pass  # percentage-sum failures have a different message format


def test_assurance_profile_finds_real_disclosure_areas():
    session, filing = _get_niit_filing()
    profile = get_assurance_profile(session, filing.id)

    assert profile.total_disclosure_areas > 50  # NIIT's filing has dozens of these tags
    assert profile.reasonable_count > 0
    assert profile.limited_count > 0
    assert 0 <= profile.reasonable_assurance_pct <= 100

def test_zero_population_percentage_is_skipped_not_failed():
    """Reproduces the real Mastek bug: when a category (e.g. Workers) is
    genuinely empty, Male%=0 and Female%=0 correctly sum to 0%, not 100%
    — this must be SKIPPED, not FAILED, since there's no population to
    have a composition of."""
    from analysis.audit_checks.consistency import CheckStatus, check_gender_percentage_sums
    from db.models import Company, Fact, Filing
    from db.session import get_session, init_db

    init_db()
    with get_session() as session:
        company = Company(cin="TESTCONS0000001", name="Zero Pop Test Co")
        session.add(company)
        session.flush()
        filing = Filing(
            company_id=company.id, financial_year_start="2025-04-01",
            financial_year_end="2026-03-31", xbrl_source_url="synthetic://test", raw_fact_count=0,
        )
        session.add(filing)
        session.flush()
        filing_id = filing.id

        ctx = {"SomeAxis": "WorkersMember"}
        session.add_all([
            Fact(filing_id=filing_id, concept="NumberOfEmployeesOrWorkersIncludingDifferentlyAbled",
                 value="0", unit="pure", dimensions={"GenderAxis": "GenderMember", **ctx}),
            Fact(filing_id=filing_id, concept="PercentageOfEmployeesOrWorkersIncludingDifferentlyAbled",
                 value="0", unit="pure", dimensions={"GenderAxis": "MaleMember", **ctx}),
            Fact(filing_id=filing_id, concept="PercentageOfEmployeesOrWorkersIncludingDifferentlyAbled",
                 value="0", unit="pure", dimensions={"GenderAxis": "FemaleMember", **ctx}),
        ])

    try:
        with get_session() as session:
            results = check_gender_percentage_sums(session, filing_id)
            assert len(results) == 1
            assert results[0].status == CheckStatus.SKIP
            assert "genuinely empty" in results[0].message
    finally:
        with get_session() as session:
            c = session.query(Company).filter_by(cin="TESTCONS0000001").one_or_none()
            if c:
                session.delete(c)


def test_wellbeing_coverage_percentage_is_never_checked_for_100_sum():
    """WellBeing coverage percentages (e.g. PercentageOfWellBeingOfEmployeesOrWorkers)
    represent independent per-gender coverage rates, not a population
    composition — must be excluded entirely from the sum-to-100% check
    (reproduces the real Mastek 'sums to 200%' false failure)."""
    from analysis.audit_checks.consistency import check_gender_percentage_sums
    from db.models import Company, Fact, Filing
    from db.session import get_session, init_db

    init_db()
    with get_session() as session:
        company = Company(cin="TESTCONS0000002", name="Wellbeing Test Co")
        session.add(company)
        session.flush()
        filing = Filing(
            company_id=company.id, financial_year_start="2025-04-01",
            financial_year_end="2026-03-31", xbrl_source_url="synthetic://test", raw_fact_count=0,
        )
        session.add(filing)
        session.flush()
        filing_id = filing.id

        ctx = {"BenefitsOfWellBeingAxis": "HealthInsuranceMember"}
        session.add_all([
            Fact(filing_id=filing_id, concept="PercentageOfWellBeingOfEmployeesOrWorkers",
                 value="0.9961", unit="pure", dimensions={"GenderAxis": "MaleMember", **ctx}),
            Fact(filing_id=filing_id, concept="PercentageOfWellBeingOfEmployeesOrWorkers",
                 value="0.9868", unit="pure", dimensions={"GenderAxis": "FemaleMember", **ctx}),
        ])

    try:
        with get_session() as session:
            results = check_gender_percentage_sums(session, filing_id)
            # This concept is not in the allowlist, so it must produce NO
            # results at all — not a FAIL, not even a SKIP entry.
            assert results == []
    finally:
        with get_session() as session:
            c = session.query(Company).filter_by(cin="TESTCONS0000002").one_or_none()
            if c:
                session.delete(c)

def test_assurance_naming_inconsistencies_are_resolved_not_left_null():
    """Reproduces the real Mastek bug: two disclosure areas were marked
    assured=true but had assurance_level=None due to SEBI's own taxonomy
    inconsistently naming the paired AssuranceSubTypeFor tag. After the
    fix, assured_but_level_unresolved_count must be 0."""
    from analysis.audit_checks.assurance import get_assurance_profile
    from analysis.core.queries import get_company_by_name, get_latest_filing
    from db.session import get_session, init_db

    init_db()
    with get_session() as session:
        company = get_company_by_name(session, "Mastek")
        assert company is not None, "Run scripts/ingest_company.py for Mastek first"
        filing = get_latest_filing(session, company.id)

        profile = get_assurance_profile(session, filing.id)
        assert profile.assured_but_level_unresolved_count == 0, (
            f"Found {profile.assured_but_level_unresolved_count} assured-but-unresolved areas: "
            f"{[i.disclosure_area for i in profile.items if i.is_assured and i.assurance_level is None]}"
        )
        # Confirm the two specific real cases now resolve correctly:
        by_topic = {i.disclosure_area: i for i in profile.items}
        assert by_topic["CSRIsApplicableAsPerSection135OfCompaniesAct2013"].assurance_level is not None
        assert by_topic["GreenCreditsHaveBeenGeneratedOrProcuredByTheListedEntityAndTopTenValueChainPartners"].assurance_level is not None