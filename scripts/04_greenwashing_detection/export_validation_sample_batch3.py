"""
Batch 3 of the vagueness-validation sample. The checked-in export contains
70 new segments, excluding texts already present in batches 1 and 2.
"""
from __future__ import annotations

import csv
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from analysis.vagueness.vagueness_combined import analyze_combined_vagueness
from db.models import Company, Fact, Filing
from db.session import get_session, init_db

BATCH1_PATH = Path("data/validation/vagueness_validation_sample.csv")
BATCH2_PATH = Path("data/validation/vagueness_validation_sample_batch2.csv")
OUTPUT_PATH = Path("data/validation/vagueness_validation_sample_batch3.csv")
MIN_TEXT_LENGTH = 30
RANDOM_SEED = 999
SAMPLE_SIZE = 100


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


def load_existing_texts() -> set[str]:
    existing = set()
    for path in [BATCH1_PATH, BATCH2_PATH]:
        if path.exists():
            with open(path, encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    existing.add(row["text"].strip())
    return existing


def main():
    init_db()
    existing_texts = load_existing_texts()
    print(f"Excluding {len(existing_texts)} texts already present in Batch 1 & 2")

    with get_session() as session:
        deduplicated = collect_deduplicated_texts(session, company_limit=400)
        deduplicated = [(name, text) for name, text in deduplicated if text.strip() not in existing_texts]
        rng = random.Random(RANDOM_SEED)
        rng.shuffle(deduplicated)
        candidates = deduplicated[:400]
        print(f"Sampling from candidate subset: {len(candidates)} segments...")

        buckets: dict[str, list[tuple[str, str, str]]] = {
            "none": [], "lexicon_only": [], "semantic_only": [], "both": [], "evasion_url": []
        }
        for company_name, text in candidates:
            result = analyze_combined_vagueness(text)
            buckets[result.flag_source].append((company_name, text, result.flag_source))

        for bucket in buckets.values():
            rng.shuffle(bucket)

        # Stratified sampling for 100 items: ~35 none, ~15 lexicon_only, ~15 semantic_only, ~30 both, ~5 evasion
        sample = []
        sample += buckets["none"][:35]
        sample += buckets["lexicon_only"][:15]
        sample += buckets["semantic_only"][:15]
        sample += buckets["both"][:30]
        sample += buckets["evasion_url"][:5]

        rng.shuffle(sample)

        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(OUTPUT_PATH, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["company_name", "text", "model_flagged", "flag_source", "human_label"])
            for company_name, text, flag_source in sample:
                model_flagged = 1 if flag_source != "none" else 0
                writer.writerow([company_name, text, model_flagged, flag_source, ""])

        print(f"\nSuccessfully exported {len(sample)} NEW segments to {OUTPUT_PATH}")
        print(f"Drawn breakdown: none={len(buckets['none'][:35])}, "
              f"lexicon_only={len(buckets['lexicon_only'][:15])}, "
              f"semantic_only={len(buckets['semantic_only'][:15])}, "
              f"both={len(buckets['both'][:30])}, "
              f"evasion={len(buckets['evasion_url'][:5])}")


if __name__ == "__main__":
    main()
