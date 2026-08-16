import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from analysis.compliance_mapper import get_compliance_mapping
from analysis.queries import get_all_filings
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

            result = get_compliance_mapping(session, filing.id)
            print(f"{company.name}: overall_alignment={result.overall_compliance_alignment_pct}%")
            for principle_num in sorted(result.per_principle):
                p = result.per_principle[principle_num]
                print(f"  P{principle_num}: mean_sim={p.mean_similarity}, segments={p.segment_count}, "
                      f"weakest_sim={p.weakest_segment_similarity}")
            print()


if __name__ == "__main__":
    main()