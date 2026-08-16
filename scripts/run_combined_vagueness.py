"""
Runs the combined (lexicon + semantic) vagueness detector across all
narrative text in the database, and reports summary statistics — how many
segments are flagged by lexicon only, semantic only, both, or neither.
This is the ablation-style breakdown the paper needs to justify having
both layers rather than just one.

DEDUPLICATION: uses the same (company, concept, text) methodology as
build_training_dataset.py — see that module's docstring for the full
rationale. Without this, boilerplate text that SEBI's form structure
replicates across multiple PrincipleAxis values within one company (e.g.
a policy statement filed once but tagged to all 9 principles) gets
counted once per replication instead of once, skewing the flag-source
percentages. This was caught by inspection: an earlier un-deduplicated
run returned the exact same NIIT paragraph as all 5 "semantic_only
examples," which is a duplication artifact, not 5 independent findings.
"""
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from analysis.vagueness_combined import analyze_combined_vagueness
from db.models import Company, Fact, Filing
from db.session import get_session, init_db

MIN_TEXT_LENGTH = 30


def collect_deduplicated_texts(session, company_limit: int) -> list[tuple[str, str]]:
    """Returns [(company_name, text), ...] with each (company, exact text)
    pair appearing only once, regardless of how many PrincipleAxis values
    it was tagged under."""
    companies = session.query(Company).limit(company_limit).all()
    results = []

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

        seen_texts = set()
        for f in text_facts:
            text = f.value.strip()
            if len(text) < MIN_TEXT_LENGTH or text in seen_texts:
                continue
            seen_texts.add(text)
            results.append((company.name, text))

    return results


def main():
    init_db()
    with get_session() as session:
        deduplicated = collect_deduplicated_texts(session, company_limit=30)

        source_counts = Counter()
        examples_by_source = defaultdict(list)

        for company_name, text in deduplicated:
            result = analyze_combined_vagueness(text)
            source_counts[result.flag_source] += 1

            if len(examples_by_source[result.flag_source]) < 5:
                examples_by_source[result.flag_source].append((company_name, text))

        total = len(deduplicated)
        print(f"Total UNIQUE (company, text) segments analyzed: {total}\n")
        print("Flag source breakdown:")
        for source, count in source_counts.most_common():
            print(f"  {source}: {count} ({count/total*100:.1f}%)")

        print("\n=== Examples flagged ONLY by semantic layer (lexicon missed these) ===")
        for company_name, text in examples_by_source["semantic_only"]:
            print(f"\n[{company_name}]")
            print(f"  {text[:200]}...")

        print("\n=== Examples flagged by BOTH layers ===")
        for company_name, text in examples_by_source["both"]:
            print(f"\n[{company_name}]")
            print(f"  {text[:200]}...")


if __name__ == "__main__":
    main()