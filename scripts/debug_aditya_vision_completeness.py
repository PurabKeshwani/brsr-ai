"""
Diagnostic — investigates why Aditya Vision Limited's completeness score
(14.19%) is a large outlier compared to other companies (57-64%). Checks
whether this reflects genuinely sparse filing, or whether the
_is_non_trivial filter is incorrectly discarding valid short answers.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from analysis.completeness_score import _is_non_trivial
from analysis.queries import get_all_filings
from db.models import Company, Fact
from db.session import get_session, init_db


def main():
    init_db()
    with get_session() as session:
        company = session.query(Company).filter(Company.name.ilike("%Aditya Vision%")).first()
        filing = get_all_filings(session, company.id)[0]

        all_facts = session.query(Fact).filter_by(filing_id=filing.id).all()
        print(f"Total raw facts in this filing: {len(all_facts)}")
        print(f"Distinct concepts (any value): {len(set(f.concept for f in all_facts))}")

        trivial_count = 0
        non_trivial_count = 0
        trivial_examples = []
        for f in all_facts:
            if _is_non_trivial(f.value):
                non_trivial_count += 1
            else:
                trivial_count += 1
                if len(trivial_examples) < 15:
                    trivial_examples.append((f.concept, f.value))

        print(f"Facts classified non-trivial: {non_trivial_count}")
        print(f"Facts classified trivial: {trivial_count}")

        print("\nSample of facts marked TRIVIAL (check if any look like valid answers):")
        for concept, value in trivial_examples:
            print(f"  {concept}: {value!r}")

        # Specifically check the two suspicious "missing" concepts
        for concept_name in ["AddressOfCorporateOfficeOfCompany", "AddressOfRegisteredOfficeOfCompany"]:
            matching = [f for f in all_facts if f.concept == concept_name]
            if matching:
                print(f"\n{concept_name}: FOUND, value={matching[0].value!r}, is_non_trivial={_is_non_trivial(matching[0].value)}")
            else:
                print(f"\n{concept_name}: NOT PRESENT in raw facts at all")


if __name__ == "__main__":
    main()