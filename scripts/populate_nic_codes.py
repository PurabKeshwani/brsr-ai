"""
Populates Company.nic_code and derived sector classification for all
ingested companies, using NICCodeOfProductOrServiceSoldByTheEntity from
each company's latest filing. A gap flagged early in this project
(deferred until now) — see conversation history.

A company may report multiple NIC codes (multiple products/services); the
FIRST one encountered is used as the primary sector classification, since
BRSR's own field ordering typically lists the primary business activity
first — this is a simplification disclosed here, not a guarantee of
correctness for diversified conglomerates.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from analysis.queries import get_all_filings
from db.models import Company, Fact
from db.session import get_session, init_db

NIC_CONCEPT = "NICCodeOfProductOrServiceSoldByTheEntity"


def main():
    init_db()
    with get_session() as session:
        companies = session.query(Company).all()
        updated = 0
        missing = 0

        for company in companies:
            filings = get_all_filings(session, company.id)
            if not filings:
                continue
            filing = filings[0]

            nic_fact = (
                session.query(Fact)
                .filter(Fact.filing_id == filing.id, Fact.concept == NIC_CONCEPT)
                .first()
            )

            if nic_fact and nic_fact.value.strip():
                company.nic_code = nic_fact.value.strip()
                updated += 1
            else:
                missing += 1

        session.commit()
        print(f"Updated NIC code for {updated} companies")
        print(f"Missing NIC code for {missing} companies")


if __name__ == "__main__":
    main()