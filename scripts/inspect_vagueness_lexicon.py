"""
Verification script — runs the hedging lexicon + KPI detector against real
narrative text from ingested BRSR filings, to check the lexicon actually
fires on genuine ESG hedging language and doesn't produce absurd results
(e.g. flagging everything, or nothing) before building the semantic layer
on top of it.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from analysis.vagueness_lexicon import analyze_vagueness
from db.models import Company, Fact, Filing
from db.session import get_session, init_db


def main():
    init_db()
    with get_session() as session:
        companies = session.query(Company).limit(15).all()

        total_texts = 0
        flagged_vague = 0
        has_kpi_count = 0
        has_hedging_count = 0

        examples_flagged = []
        examples_clean_with_kpi = []

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

            for f in text_facts:
                text = f.value.strip()
                if len(text) < 30:
                    continue

                total_texts += 1
                result = analyze_vagueness(text)

                if result.has_kpi:
                    has_kpi_count += 1
                if result.hedging_terms_found:
                    has_hedging_count += 1
                if result.is_flagged_vague:
                    flagged_vague += 1
                    if len(examples_flagged) < 5:
                        examples_flagged.append((company.name, result))
                elif result.has_kpi and len(examples_clean_with_kpi) < 3:
                    examples_clean_with_kpi.append((company.name, result))

        print(f"Total narrative text segments analyzed: {total_texts}")
        print(f"Segments with at least one hedging term: {has_hedging_count} ({has_hedging_count/total_texts*100:.1f}%)")
        print(f"Segments with at least one KPI/numeric entity: {has_kpi_count} ({has_kpi_count/total_texts*100:.1f}%)")
        print(f"Segments FLAGGED as vague (hedging + no KPI): {flagged_vague} ({flagged_vague/total_texts*100:.1f}%)")

        print("\n=== Example FLAGGED (vague) segments ===")
        for company_name, result in examples_flagged:
            print(f"\n[{company_name}]")
            print(f"  Hedging terms: {result.hedging_terms_found}")
            print(f"  Text: {result.text[:200]}...")

        print("\n=== Example NOT flagged (has KPI) segments ===")
        for company_name, result in examples_clean_with_kpi:
            print(f"\n[{company_name}]")
            print(f"  KPI matches: {result.kpi_matches}")
            print(f"  Text: {result.text[:200]}...")


if __name__ == "__main__":
    main()