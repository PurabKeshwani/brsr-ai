"""
Exports a stratified sample of 30 unique narrative-text segments for
manual human validation of the combined vagueness detector — the
ground-truth labels needed to compute precision/recall/AUC-ROC, which
cannot be claimed without them (see conversation: the report's stated
AUC-ROC=0.89 requires labeled data that does not exist for this weakly-
supervised pipeline; this script builds a small, honestly-scoped one).

Sampling strategy: stratified across confidence bands (not random) so the
validation set includes genuinely ambiguous/borderline cases, not just
easy ones — a validation set of only obvious examples would inflate
apparent accuracy.

Output: data/validation/vagueness_validation_sample.csv with columns
[company_name, text, model_flagged, flag_source, human_label] — the last
column is left EMPTY for manual annotation (fill with 1 = genuinely vague,
0 = genuinely fine, per the annotator's own judgment).
"""
import csv
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from analysis.vagueness.vagueness_combined import analyze_combined_vagueness
from db.models import Company, Fact, Filing
from db.session import get_session, init_db

OUTPUT_PATH = Path("data/validation/vagueness_validation_sample.csv")
MIN_TEXT_LENGTH = 30
RANDOM_SEED = 42
SAMPLE_SIZE = 30


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


def main():
    init_db()
    with get_session() as session:
        deduplicated = collect_deduplicated_texts(session, company_limit=30)

        # Bucket by flag_source — this gives us strata: "none" = model says
        # clearly fine, "both" = model very confident it's vague,
        # "lexicon_only"/"semantic_only" = each layer's unique catches,
        # i.e. the more borderline/disagreement-prone cases.
        buckets: dict[str, list[tuple[str, str, str]]] = {
            "none": [], "lexicon_only": [], "semantic_only": [], "both": [],
        }
        for company_name, text in deduplicated:
            result = analyze_combined_vagueness(text)
            buckets[result.flag_source].append((company_name, text, result.flag_source))

        rng = random.Random(RANDOM_SEED)
        for bucket in buckets.values():
            rng.shuffle(bucket)

        # Stratified sample: 10 from "none" (should mostly be genuinely
        # fine — sanity check on false-positive rate), 10 split across
        # lexicon_only/semantic_only (the borderline/disagreement cases,
        # most informative for validation), 10 from "both" (should mostly
        # be genuinely vague — sanity check on true-positive confidence).
        sample = []
        sample += buckets["none"][:10]
        sample += buckets["lexicon_only"][:5]
        sample += buckets["semantic_only"][:5]
        sample += buckets["both"][:10]

        rng.shuffle(sample)  # so the annotator can't infer the model's answer from row order

        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(OUTPUT_PATH, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["company_name", "text", "model_flagged", "flag_source", "human_label"])
            for company_name, text, flag_source in sample:
                model_flagged = 1 if flag_source != "none" else 0
                writer.writerow([company_name, text, model_flagged, flag_source, ""])

        print(f"Exported {len(sample)} segments to {OUTPUT_PATH}")
        print(f"Bucket sizes drawn from: none={len(buckets['none'])}, "
              f"lexicon_only={len(buckets['lexicon_only'])}, "
              f"semantic_only={len(buckets['semantic_only'])}, "
              f"both={len(buckets['both'])}")
        print("\nNext step: open the CSV, read each 'text' cell, and fill "
              "'human_label' with 1 (genuinely vague/unsubstantiated) or "
              "0 (genuinely fine/specific) based on your own judgment — "
              "WITHOUT looking at the 'model_flagged' column while deciding.")


if __name__ == "__main__":
    main()
