"""
Diagnostic script — checks how much labeled narrative text we actually
have across all ingested companies before building the training pipeline
around it. Verifies the core assumption behind Phase B: that
ExplanatoryTextBlock facts reliably carry a PrincipleAxis dimension we can
use as a free label, without manual annotation.

Run this BEFORE writing any dataset-building code — if the assumption
doesn't hold across companies (not just NIIT), the whole BERT training
plan needs rethinking before more time is spent on it.
"""
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from db.models import Company, Fact, Filing
from db.session import get_session, init_db


def main():
    init_db()
    with get_session() as session:
        companies = session.query(Company).all()
        print(f"Total companies in DB: {len(companies)}\n")

        total_text_facts = 0
        has_principle_axis = 0
        principle_value_counts = Counter()
        companies_with_zero_labeled = []

        for company in companies:
            filing = (
                session.query(Filing)
                .filter_by(company_id=company.id)
                .order_by(Filing.financial_year_end.desc())
                .first()
            )
            if filing is None:
                continue

            text_facts = (
                session.query(Fact)
                .filter(Fact.filing_id == filing.id, Fact.concept.like("%ExplanatoryTextBlock%"))
                .all()
            )
            total_text_facts += len(text_facts)

            company_labeled_count = 0
            for f in text_facts:
                principle = f.dimensions.get("PrincipleAxis")
                if principle:
                    has_principle_axis += 1
                    company_labeled_count += 1
                    principle_value_counts[principle] += 1

            if company_labeled_count == 0:
                companies_with_zero_labeled.append(company.name)

        print(f"Total ExplanatoryTextBlock facts across all companies: {total_text_facts}")
        print(f"Facts WITH a PrincipleAxis dimension: {has_principle_axis} "
              f"({has_principle_axis / total_text_facts * 100:.1f}%)" if total_text_facts else "N/A")
        print(f"\nCompanies with ZERO PrincipleAxis-labeled text: {len(companies_with_zero_labeled)}")
        for name in companies_with_zero_labeled[:10]:
            print(f"  - {name}")

        print(f"\nDistribution across Principle values found:")
        for principle, count in sorted(principle_value_counts.items()):
            print(f"  {principle}: {count}")


if __name__ == "__main__":
    main()
