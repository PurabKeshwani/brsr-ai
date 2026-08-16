"""
Diagnostic — identifies which ExplanatoryTextBlock concepts have text that
is duplicated ACROSS DIFFERENT PrincipleAxis values within the same
company's filing. This is the real root cause investigation for the BERT
training failure: verified evidence showed 1,212 of 1,648 training rows
(73%) were exact-duplicate text assigned conflicting principle labels
(e.g. the same boilerplate sentence tagged as both Principle1 and
Principle7), which is pure label noise a classifier cannot learn from.

This script identifies exactly which XBRL concepts are the source of that
noise, so they can be excluded from the training dataset builder rather
than guessed at.
"""
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from db.models import Company, Fact, Filing
from db.session import get_session, init_db

PRINCIPLE_TO_LABEL = {f"Principle{i}Member": i for i in range(1, 10)}
MIN_TEXT_LENGTH = 20


def main():
    init_db()
    with get_session() as session:
        companies = session.query(Company).all()

        concept_dup_instances = defaultdict(int)
        concept_total_texts = defaultdict(int)

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

            by_concept_text = defaultdict(set)
            for f in text_facts:
                principle = f.dimensions.get("PrincipleAxis")
                text = f.value.strip()
                if principle in PRINCIPLE_TO_LABEL and len(text) >= MIN_TEXT_LENGTH:
                    by_concept_text[(f.concept, text)].add(principle)
                    concept_total_texts[f.concept] += 1

            for (concept, text), principles in by_concept_text.items():
                if len(principles) > 1:
                    concept_dup_instances[concept] += len(principles)

        print(f"{'Concept':<90} {'DupInstances':<14} {'Total':<8} {'Dup%'}")
        print("-" * 120)
        for concept in sorted(concept_total_texts, key=lambda c: -concept_total_texts[c]):
            dup = concept_dup_instances.get(concept, 0)
            total = concept_total_texts[concept]
            pct = dup / total * 100 if total else 0
            print(f"{concept:<90} {dup:<14} {total:<8} {pct:.0f}%")


if __name__ == "__main__":
    main()