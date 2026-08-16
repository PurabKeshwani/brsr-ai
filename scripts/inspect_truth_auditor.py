import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from analysis.queries import get_all_filings
from analysis.truth_auditor import run_truth_audit
from db.models import Company
from db.session import get_session, init_db


def main():
    init_db()
    with get_session() as session:
        for name in ["NIIT Learning", "Mastek", "Coal India"]:
            company = session.query(Company).filter(Company.name.ilike(f"%{name}%")).first()
            if company is None:
                continue
            filing = get_all_filings(session, company.id)[0]

            report = run_truth_audit(session, filing.id)
            print(report.summary())
            print(f"  High-confidence contradiction found: {report.has_high_confidence_contradiction}")
            print()


if __name__ == "__main__":
    main()