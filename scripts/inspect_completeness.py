"""
Verification — computes the Completeness score for a handful of real
ingested companies, to sanity-check the concept-universe approach before
building it into the full Transparency Score.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from analysis.completeness_score import get_completeness_score, get_concept_universe
from analysis.queries import get_all_filings
from db.models import Company
from db.session import get_session, init_db


def main():
    init_db()
    with get_session() as session:
        universe = get_concept_universe(session)
        print(f"Concept universe size (union across all ingested filings): {len(universe)}\n")

        sample_names = ["NIIT Learning", "Mastek", "Coal India", "Aditya Vision"]
        for name in sample_names:
            company = session.query(Company).filter(Company.name.ilike(f"%{name}%")).first()
            if company is None:
                print(f"{name}: not found")
                continue
            filings = get_all_filings(session, company.id)
            if not filings:
                continue
            filing = filings[0]

            result = get_completeness_score(session, filing.id, universe=universe)
            print(f"{company.name}:")
            print(f"  Filed concepts: {result.filed_concept_count} / {result.universe_size}")
            print(f"  Completeness: {result.completeness_pct}%")
            print(f"  Sample missing concepts: {result.missing_concepts[:5]}")
            print()


if __name__ == "__main__":
    main()