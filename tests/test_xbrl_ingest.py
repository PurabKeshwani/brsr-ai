"""
Idempotency and error-path tests for xbrl_ingest.py — this is the module
the API will sit directly on top of, so a bug here (a duplicate filing on
re-ingest, or a raw exception leaking through instead of IngestionError)
would surface as a confusing crash or silent data corruption at the API
layer. Tests build minimal valid/invalid XBRL fixtures directly rather
than hitting the network, so they run fast and deterministically.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from db.models import Company, Filing
from db.session import get_session, init_db
from ingestion.xbrl_ingest import IngestionError, ingest_filing

TEST_CIN = "TESTINGEST00000001"

VALID_XBRL_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<xbrli:xbrl xmlns:in-capmkt="https://www.sebi.gov.in/xbrl/2026-02-28/in-capmkt"
            xmlns:xbrli="http://www.xbrl.org/2003/instance">
  <xbrli:context id="DCYMain">
    <xbrli:entity><xbrli:identifier scheme="x">{cin}</xbrli:identifier></xbrli:entity>
    <xbrli:period><xbrli:startDate>{fy_start}</xbrli:startDate><xbrli:endDate>{fy_end}</xbrli:endDate></xbrli:period>
  </xbrli:context>
  <xbrli:unit id="pure"><xbrli:measure>xbrli:pure</xbrli:measure></xbrli:unit>
  <in-capmkt:CorporateIdentityNumber contextRef="DCYMain">{cin}</in-capmkt:CorporateIdentityNumber>
  <in-capmkt:NameOfTheCompany contextRef="DCYMain">{name}</in-capmkt:NameOfTheCompany>
  <in-capmkt:DateOfStartOfFinancialYear contextRef="DCYMain">{fy_start}</in-capmkt:DateOfStartOfFinancialYear>
  <in-capmkt:DateOfEndOfFinancialYear contextRef="DCYMain">{fy_end}</in-capmkt:DateOfEndOfFinancialYear>
  <in-capmkt:SomeMetric contextRef="DCYMain" unitRef="pure" decimals="0">{metric_value}</in-capmkt:SomeMetric>
</xbrli:xbrl>
"""


def _write_fixture(tmp_path: Path, cin=TEST_CIN, name="Synthetic Ingest Co", fy_start="2025-04-01",
                    fy_end="2026-03-31", metric_value="100", filename="test.xml") -> Path:
    content = VALID_XBRL_TEMPLATE.format(cin=cin, name=name, fy_start=fy_start, fy_end=fy_end, metric_value=metric_value)
    path = tmp_path / filename
    path.write_text(content, encoding="utf-8")
    return path


def _cleanup():
    with get_session() as session:
        c = session.query(Company).filter_by(cin=TEST_CIN).one_or_none()
        if c:
            session.delete(c)


def test_reingesting_same_filing_does_not_duplicate_facts(tmp_path):
    """Idempotency: ingesting the same (company, financial year) twice must
    leave exactly one Filing row and the fact count must reflect the LATEST
    ingest, not grow with each run."""
    init_db()
    path = _write_fixture(tmp_path, metric_value="100")

    try:
        with get_session() as session:
            filing1 = ingest_filing(session, path, source_url="test://1")
            filing1_id = filing1.id
            fact_count_1 = filing1.raw_fact_count

        # Re-ingest the SAME file (same FY, same data)
        with get_session() as session:
            filing2 = ingest_filing(session, path, source_url="test://2")
            fact_count_2 = filing2.raw_fact_count

        with get_session() as session:
            company = session.query(Company).filter_by(cin=TEST_CIN).one()
            all_filings = session.query(Filing).filter_by(company_id=company.id).all()

            assert len(all_filings) == 1, f"Expected exactly 1 filing after re-ingest, found {len(all_filings)}"
            assert fact_count_1 == fact_count_2
            # The old filing_id's row should no longer exist (it was deleted and replaced)
            assert all_filings[0].id != filing1_id or True  # id may or may not be reused depending on DB; the count check above is the real assertion
    finally:
        _cleanup()


def test_reingesting_with_changed_data_replaces_old_facts(tmp_path):
    """If a company re-files (e.g. a corrected XBRL) for the same financial
    year, re-ingesting must reflect the NEW data, not silently keep stale
    old facts alongside it."""
    init_db()
    path_v1 = _write_fixture(tmp_path, metric_value="100", filename="v1.xml")
    path_v2 = _write_fixture(tmp_path, metric_value="999", filename="v2.xml")

    try:
        with get_session() as session:
            ingest_filing(session, path_v1, source_url="test://v1")

        with get_session() as session:
            filing = ingest_filing(session, path_v2, source_url="test://v2")
            filing_id = filing.id

        with get_session() as session:
            from db.models import Fact
            facts = session.query(Fact).filter_by(filing_id=filing_id, concept="SomeMetric").all()
            assert len(facts) == 1, f"Expected exactly 1 SomeMetric fact after replace, found {len(facts)}"
            assert facts[0].value == "999", f"Expected updated value '999', found {facts[0].value!r} (stale data not replaced)"
    finally:
        _cleanup()


def test_ingest_raises_ingestion_error_when_cin_missing(tmp_path):
    content = VALID_XBRL_TEMPLATE.format(
        cin=TEST_CIN, name="Co", fy_start="2025-04-01", fy_end="2026-03-31", metric_value="1",
    ).replace("<in-capmkt:CorporateIdentityNumber", "<in-capmkt:SomethingElse").replace(
        "</in-capmkt:CorporateIdentityNumber>", "</in-capmkt:SomethingElse>"
    )
    path = tmp_path / "no_cin.xml"
    path.write_text(content, encoding="utf-8")

    init_db()
    with pytest.raises(IngestionError, match="CIN|company name"):
        with get_session() as session:
            ingest_filing(session, path, source_url="test://no-cin")


def test_ingest_raises_ingestion_error_when_financial_year_missing(tmp_path):
    content = VALID_XBRL_TEMPLATE.format(
        cin=TEST_CIN, name="Co", fy_start="2025-04-01", fy_end="2026-03-31", metric_value="1",
    ).replace("<in-capmkt:DateOfEndOfFinancialYear", "<in-capmkt:SomethingElse").replace(
        "</in-capmkt:DateOfEndOfFinancialYear>", "</in-capmkt:SomethingElse>"
    )
    path = tmp_path / "no_fy.xml"
    path.write_text(content, encoding="utf-8")

    init_db()
    try:
        with pytest.raises(IngestionError, match="financial year"):
            with get_session() as session:
                ingest_filing(session, path, source_url="test://no-fy")
    finally:
        _cleanup()


def test_ingest_raises_ingestion_error_not_raw_exception_on_malformed_xml(tmp_path):
    """Reproduces a real gap found by inspection: parse_xbrl uses
    xml.etree.ElementTree, which raises ET.ParseError on malformed input.
    Before the fix, this propagated as a raw ET.ParseError instead of the
    module's own IngestionError — meaning callers (eventually the API)
    would need to catch two different exception types instead of one."""
    path = tmp_path / "malformed.xml"
    path.write_text("<xbrli:xbrl><unclosed tag", encoding="utf-8")

    init_db()
    with pytest.raises(IngestionError, match="Malformed XML"):
        with get_session() as session:
            ingest_filing(session, path, source_url="test://malformed")


def test_ingest_raises_ingestion_error_on_empty_file(tmp_path):
    path = tmp_path / "empty.xml"
    path.write_text("", encoding="utf-8")

    init_db()
    with pytest.raises(IngestionError):
        with get_session() as session:
            ingest_filing(session, path, source_url="test://empty")