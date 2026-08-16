"""
Ingests a single company's BRSR XBRL filing into the database.

Usage:
    python scripts/ingest_company.py "NIIT Learning Systems Limited" "https://nsearchives.nseindia.com/corporate/xbrl/BRSR_22067_WebXMLFile_20260814_195736768.xml"
"""
import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from db.session import get_session, init_db  # noqa: E402
from ingestion.xbrl_ingest import IngestionError, ingest_company_by_url  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("company_hint", help="Company name, used for the local XBRL cache filename")
    ap.add_argument("xbrl_url", help="URL to the company's BRSR XBRL file on NSE")
    args = ap.parse_args()

    init_db()

    try:
        with get_session() as session:
            filing = ingest_company_by_url(session, args.xbrl_url, args.company_hint)
            print(f"\nSUCCESS: ingested filing_id={filing.id} for company_id={filing.company_id}")
            print(f"  Financial year: {filing.financial_year_start} to {filing.financial_year_end}")
            print(f"  Facts stored: {filing.raw_fact_count}")
    except IngestionError as e:
        print(f"\nFAILED: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()