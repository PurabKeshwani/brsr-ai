"""
Batch 2 of the vagueness-validation sample — 50 NEW segments (different
random seed, output path, and explicit exclusion of any text already
labeled in batch 1) for expanding the labeled set used by the XGBoost
meta-classifier (see conversation history: n=30 alone is too small for
a meaningful train/test split on a tree ensemble, even with few features).
"""
import csv
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from analysis.vagueness_combined import analyze_combined_vagueness
from db.models import Company, Fact, Filing
from db.session import get_session, init_db

BATCH1_PATH = Path("data/validation/vagueness_validation_sample.csv")
OUTPUT_PATH = Path("data/validation/vagueness_validation_sample_batch2.csv")
MIN_TEXT_LENGTH = 30
RANDOM_SEED = 123  # different from batch 1's seed (42), for a genuinely different sample
SAMPLE_SIZE = 50


def collect_deduplicated_texts(session, company_limit: int) -> list[tuple[str, str]]:
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
        seen = set()
        for f in text_facts:
            text = f.value.strip()
            if len(text) < MIN_TEXT_LENGTH or text in seen:
                continue
            seen.add(text)
            results.append((company.name, text))
    return results


def load_batch1_texts() -> set[str]:
    if not BATCH1_PATH.exists():
        return set()
    with open(BATCH1_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return {row["text"] for row in reader}


def main():
    init_db()
    batch1_texts = load_batch1_texts()
    print(f"Excluding {len(batch1_texts)} texts already in batch 1")

    with get_session() as session:
        deduplicated = collect_deduplicated_texts(session, company_limit=150)  # wider pool than batch 1's 30, since we're excluding overlap
        deduplicated = [(name, text) for name, text in deduplicated if text not in batch1_texts]

        buckets: dict[str, list[tuple[str, str, str]]] = {
            "none": [], "lexicon_only": [], "semantic_only": [], "both": [],
        }
        for company_name, text in deduplicated:
            result = analyze_combined_vagueness(text)
            buckets[result.flag_source].append((company_name, text, result.flag_source))

        rng = random.Random(RANDOM_SEED)
        for bucket in buckets.values():
            rng.shuffle(bucket)

        # Same stratification proportions as batch 1, scaled to 50: ~17 none, ~8+8 lexicon/semantic-only, ~17 both
        sample = []
        sample += buckets["none"][:17]
        sample += buckets["lexicon_only"][:8]
        sample += buckets["semantic_only"][:8]
        sample += buckets["both"][:17]

        rng.shuffle(sample)

        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(OUTPUT_PATH, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["company_name", "text", "model_flagged", "flag_source", "human_label"])
            for company_name, text, flag_source in sample:
                model_flagged = 1 if flag_source != "none" else 0
                writer.writerow([company_name, text, model_flagged, flag_source, ""])

        print(f"Exported {len(sample)} NEW segments to {OUTPUT_PATH}")
        print(f"Bucket sizes drawn from: none={len(buckets['none'])}, "
              f"lexicon_only={len(buckets['lexicon_only'])}, "
              f"semantic_only={len(buckets['semantic_only'])}, "
              f"both={len(buckets['both'])}")


if __name__ == "__main__":
    main()