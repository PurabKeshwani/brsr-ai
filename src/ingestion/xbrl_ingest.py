"""
XBRL Ingestion — fetches, parses, and stores a BRSR XBRL filing in the DB.

Idempotent by design: ingesting the same (company, financial_year) twice
deletes the old facts and inserts fresh ones inside one transaction, rather
than attempting complex per-fact dedup. This makes re-runs after a bug fix
or a re-download completely safe.
"""
from __future__ import annotations

import logging
from pathlib import Path

import xml.etree.ElementTree as ET

import requests
from sqlalchemy.orm import Session

from db.models import Company, Fact, Filing
from ingestion.xbrl_parser import parse_xbrl

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept": "application/xml,text/xml,*/*",
}

XBRL_CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "xbrl"


class IngestionError(Exception):
    """Raised when a filing cannot be downloaded or parsed. Callers should
    treat this as a signal to investigate, not silently skip — see the
    project's established principle of never hiding a failure mode."""


def download_xbrl(url: str, company_hint: str) -> Path:
    """Downloads an XBRL file to a local cache, or reuses an existing copy.
    Raises IngestionError on failure — never returns a partial/corrupt file
    silently.
    """
    XBRL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = "".join(c if c.isalnum() or c in " -_" else "_" for c in company_hint)
    dest = XBRL_CACHE_DIR / f"{safe_name.strip().replace(' ', '_')[:80]}.xml"

    if dest.exists() and dest.stat().st_size > 1000:
        logger.info("Using cached XBRL for %s: %s", company_hint, dest)
        return dest

    logger.info("Downloading XBRL for %s from %s", company_hint, url)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=90)
    except requests.RequestException as e:
        raise IngestionError(f"Network error downloading {url}: {e}") from e

    if resp.status_code != 200:
        raise IngestionError(f"HTTP {resp.status_code} downloading {url}")
    if len(resp.content) < 1000:
        raise IngestionError(f"Downloaded file suspiciously small ({len(resp.content)} bytes): {url}")

    dest.write_bytes(resp.content)
    logger.info("Saved %s (%s bytes)", dest, f"{len(resp.content):,}")
    return dest


def _get_or_create_company(session: Session, cin: str, name: str) -> Company:
    company = session.query(Company).filter_by(cin=cin).one_or_none()
    if company is None:
        company = Company(cin=cin, name=name)
        session.add(company)
        session.flush()  # assigns company.id without committing the transaction
        logger.info("Created new company record: %s", company)
    return company


def _find_concept_value(facts, concept_suffix: str) -> str | None:
    """Finds the first fact whose concept name ends with the given suffix,
    regardless of dimensions — used only for company-identity fields
    (CIN, name) that are filed once per document, not per-dimension."""
    for f in facts:
        if f.concept.endswith(concept_suffix):
            return f.value
    return None


def ingest_filing(session: Session, xbrl_path: Path, source_url: str) -> Filing:
    """Parses an XBRL file and stores it in the database. If a filing for
    the same (company CIN, financial year end) already exists, its facts
    are replaced — see module docstring for the idempotency rationale.
    """
    try:
        facts = parse_xbrl(xbrl_path)
    except ET.ParseError as e:
        raise IngestionError(f"Malformed XML in {xbrl_path}: {e}") from e

    if not facts:
        raise IngestionError(f"No facts parsed from {xbrl_path} — file may be malformed")

    cin = _find_concept_value(facts, "CorporateIdentityNumber")
    name = _find_concept_value(facts, "NameOfTheCompany")
    if not cin or not name:
        raise IngestionError(
            f"Could not find CIN/company name in {xbrl_path} — "
            f"cannot identify which company this filing belongs to"
        )

    fy_end = None
    for f in facts:
        if f.concept == "DateOfEndOfFinancialYear":
            fy_end = f.value
            break
    fy_start = None
    for f in facts:
        if f.concept == "DateOfStartOfFinancialYear":
            fy_start = f.value
            break
    if not fy_end or not fy_start:
        raise IngestionError(f"Could not find financial year dates in {xbrl_path}")

    company = _get_or_create_company(session, cin=cin, name=name)

    existing = (
        session.query(Filing)
        .filter_by(company_id=company.id, financial_year_end=fy_end)
        .one_or_none()
    )
    if existing is not None:
        logger.info("Replacing existing filing for %s FY ending %s (id=%s)", name, fy_end, existing.id)
        session.delete(existing)
        session.flush()

    filing = Filing(
        company_id=company.id,
        financial_year_start=fy_start,
        financial_year_end=fy_end,
        xbrl_source_url=source_url,
        raw_fact_count=len(facts),
    )
    session.add(filing)
    session.flush()  # assigns filing.id

    fact_rows = [
        Fact(
            filing_id=filing.id,
            concept=f.concept,
            value=f.value,
            unit=f.unit,
            decimals=f.decimals,
            period_start=f.context.start_date,
            period_end=f.context.end_date,
            period_instant=f.context.instant,
            dimensions=f.dimensions,
        )
        for f in facts
    ]
    session.add_all(fact_rows)

    logger.info("Ingested %d facts for %s (FY %s to %s)", len(fact_rows), name, fy_start, fy_end)
    return filing


def ingest_company_by_url(session: Session, xbrl_url: str, company_hint: str) -> Filing:
    """Convenience wrapper: download (or reuse cache) + ingest in one call."""
    path = download_xbrl(xbrl_url, company_hint)
    return ingest_filing(session, path, source_url=xbrl_url)