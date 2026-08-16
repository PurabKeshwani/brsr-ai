import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from analysis.queries import get_company_by_name, get_gender_split, get_latest_filing, get_single_fact
from db.session import get_session, init_db


def test_niit_employee_headcount_matches_hand_verified_xbrl_output():
    """Regression test against real NIIT data we already hand-verified:
    Total=2489, Male=1282 (51.51%), Female=1206 (48.46%), Other=1."""
    init_db()
    with get_session() as session:
        company = get_company_by_name(session, "NIIT Learning")
        assert company is not None, "Run scripts/ingest_company.py for NIIT first"

        filing = get_latest_filing(session, company.id)
        assert filing is not None

        split = get_gender_split(
            session, filing.id,
            concept="NumberOfEmployeesOrWorkersIncludingDifferentlyAbled",
            category_axis="DetailsOfEmployeesAndWorkersIncludingDifferentlyAbledAxis",
            category_member="PermanentEmployeesMember",
        )

        assert split.total == 2489
        assert split.male == 1282
        assert split.female == 1206
        assert split.other == 1
        assert split.female_pct == 48.45  # 1206/2489, matches XBRL's own 0.4846 (rounding)


def test_single_fact_returns_none_for_missing_concept():
    init_db()
    with get_session() as session:
        company = get_company_by_name(session, "NIIT Learning")
        filing = get_latest_filing(session, company.id)
        result = get_single_fact(session, filing.id, "ThisConceptDoesNotExist")
        assert result is None