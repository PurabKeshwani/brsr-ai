"""
Phase B — Dataset Builder

Extracts every PrincipleAxis-labeled ExplanatoryTextBlock fact across all
ingested companies' latest filings, and builds a stratified train/
validation/test split for BERT fine-tuning.

This is a genuine methodological departure from manual annotation (the
approach describing 12,340 hand-labeled segments with Cohen's Kappa
inter-annotator agreement): labels here come directly from SEBI's own
XBRL taxonomy (the PrincipleAxis dimension), which every filer tags
consistently as part of mandatory disclosure — see
scripts/inspect_principle_labels.py for the verification that this
assumption holds across all currently-ingested companies (0 companies
found with zero labeled text). This should be described in the paper as
"weak supervision from regulatory taxonomy structure" rather than manual
annotation — it is a different (and arguably more scalable, more
reproducible) labeling methodology, not an inferior substitute.

DEDUPLICATION METHODOLOGY (corrects an earlier over-aggressive attempt —
see conversation history): the correct unit of deduplication is
(company, concept, exact text), not "concept" alone. A first attempt
blanket-excluded 5 concepts identified as having a high rate of
cross-principle duplication (78-95%), which discarded ~99% of the dataset
(2,332 of 2,360 samples) — those same concepts turned out to also hold
most of the genuinely principle-specific content, since a real minority
of companies write distinct text per principle even in these fields.
Instead: for each company, group text facts by (concept, exact text) and
discard only the specific combinations that were tagged under MORE THAN
ONE PrincipleAxis value for that company (contradictory-label noise,
verified root cause of the original BERT training failure — eval_loss
stuck at ln(9), the random-guess baseline, across all 4 epochs). Text
appearing under exactly one principle is kept regardless of which concept
it came from.

Output: three CSV files (train/val/test) with columns [text, label,
principle_id, company_name, cin] — label is 0-8 (Principle1..9 mapped to
0..8) for direct use with a HuggingFace-style classification head.
"""
from __future__ import annotations

import csv
import random
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from db.models import Company, Fact, Filing
from db.session import get_session, init_db

OUTPUT_DIR = Path("data/training")
TRAIN_RATIO, VAL_RATIO, TEST_RATIO = 0.70, 0.15, 0.15
RANDOM_SEED = 42  # fixed for reproducibility, per standard ML practice

PRINCIPLE_TO_LABEL = {f"Principle{i}Member": i - 1 for i in range(1, 10)}  # Principle1Member -> 0, ..., Principle9Member -> 8

MIN_TEXT_LENGTH = 20  # characters — discards near-empty or placeholder text blocks


def collect_labeled_samples(session) -> list[dict]:
    """Collects PrincipleAxis-labeled text, discarding only the SPECIFIC
    (company, concept, text) combinations that are genuinely duplicated
    across multiple principles within that company's filing — not entire
    concepts. See module docstring for the full rationale."""
    samples = []
    companies = session.query(Company).all()

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

        # Group by (concept, text) -> set of principles this exact text
        # was tagged with, within THIS company's filing.
        by_concept_text: dict[tuple[str, str], set[str]] = defaultdict(set)
        for f in text_facts:
            principle_dim = f.dimensions.get("PrincipleAxis")
            text = f.value.strip()
            if principle_dim in PRINCIPLE_TO_LABEL and len(text) >= MIN_TEXT_LENGTH:
                by_concept_text[(f.concept, text)].add(principle_dim)

        for (concept, text), principles in by_concept_text.items():
            if len(principles) > 1:
                continue  # genuinely duplicated across principles for this company — discard, contradictory label
            principle_dim = next(iter(principles))  # exactly one — safe to use as the label
            samples.append({
                "text": text,
                "label": PRINCIPLE_TO_LABEL[principle_dim],
                "principle_id": principle_dim,
                "company_name": company.name,
                "cin": company.cin,
            })

    return samples


def stratified_split(samples: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    """Splits samples into train/val/test, preserving each class's
    proportion in every split (stratified sampling) — matches the
    approach described for the original 12,340-segment dataset, applied
    here to our weakly-supervised set instead."""
    by_label = defaultdict(list)
    for s in samples:
        by_label[s["label"]].append(s)

    rng = random.Random(RANDOM_SEED)
    train, val, test = [], [], []

    for label, group in by_label.items():
        rng.shuffle(group)
        n = len(group)
        n_train = int(n * TRAIN_RATIO)
        n_val = int(n * VAL_RATIO)

        train.extend(group[:n_train])
        val.extend(group[n_train : n_train + n_val])
        test.extend(group[n_train + n_val :])

    rng.shuffle(train)
    rng.shuffle(val)
    rng.shuffle(test)
    return train, val, test


def write_csv(path: Path, samples: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["text", "label", "principle_id", "company_name", "cin"])
        writer.writeheader()
        writer.writerows(samples)


def main():
    init_db()
    with get_session() as session:
        samples = collect_labeled_samples(session)

    print(f"Total labeled samples collected: {len(samples)}")

    label_counts = defaultdict(int)
    for s in samples:
        label_counts[s["principle_id"]] += 1
    print("Per-principle counts (post dedup + min-length filter):")
    for principle, count in sorted(label_counts.items()):
        print(f"  {principle}: {count}")

    train, val, test = stratified_split(samples)
    print(f"\nSplit sizes — train: {len(train)}, val: {len(val)}, test: {len(test)}")

    write_csv(OUTPUT_DIR / "train.csv", train)
    write_csv(OUTPUT_DIR / "val.csv", val)
    write_csv(OUTPUT_DIR / "test.csv", test)
    print(f"\nWritten to {OUTPUT_DIR}/train.csv, val.csv, test.csv")


if __name__ == "__main__":
    main()