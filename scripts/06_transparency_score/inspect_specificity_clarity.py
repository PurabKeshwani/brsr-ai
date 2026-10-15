import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from analysis.core.queries import get_all_filings
from analysis.scoring.specificity_clarity_score import get_specificity_clarity_score
from db.models import Company
from db.session import get_session, init_db


def main():
    init_db()
    with get_session() as session:
        sample_names = ["NIIT Learning", "Mastek", "Coal India", "Aditya Vision"]
        for name in sample_names:
            company = session.query(Company).filter(Company.name.ilike(f"%{name}%")).first()
            if company is None:
                continue
            filing = get_all_filings(session, company.id)[0]

            result = get_specificity_clarity_score(session, filing.id)
            print(f"{company.name}:")
            print(f"  Total segments: {result.total_segments}")
            print(f"  Segments with KPI: {result.segments_with_kpi} -> Specificity: {result.specificity_pct}%")
            print(f"  Segments flagged vague: {result.segments_flagged_vague} -> Clarity: {result.clarity_pct}%")
            print()


if __name__ == "__main__":
    main()
