"""
Human Validation Study — Sample Export (Transparency Score, Pearson-r)

Selects 20 companies STRATIFIED across the full Transparency Score
distribution (already computed in data/analysis/transparency_scores.csv)
— not randomly, so the correlation study covers the full range rather
than clustering near the mean, which would understate any real
relationship. For each company, exports a readable summary of its
disclosure (representative narrative segments, not the raw AI score) for
a human reader to independently rate 0-100 on overall disclosure quality,
matching the report's stated validation methodology (5.5.3) — with the
key difference that this project discloses whether the rating was done
by a person or was LLM-assisted, per the project's evidence-first
practice.
"""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import pandas as pd

from analysis.core.queries import get_all_filings
from db.models import Company, Fact
from db.session import get_session, init_db

SCORES_PATH = Path("data/analysis/transparency_scores.csv")
OUTPUT_SUMMARY_PATH = Path("data/validation/human_score_validation_summaries.txt")
OUTPUT_CSV_PATH = Path("data/validation/human_score_validation.csv")

N_COMPANIES = 20
MIN_TEXT_LENGTH = 30
MAX_SEGMENTS_PER_COMPANY = 10  # enough to form an impression without reading the entire filing


def select_stratified_sample(scores_df: pd.DataFrame, n: int) -> pd.DataFrame:
    """Splits the score range into n bins and picks one company per bin
    (closest to that bin's center) — guarantees coverage across the full
    range rather than random clustering near the mean."""
    sorted_df = scores_df.sort_values("transparency_score").reset_index(drop=True)
    indices = [round(i * (len(sorted_df) - 1) / (n - 1)) for i in range(n)]
    return sorted_df.iloc[indices].reset_index(drop=True)


def main():
    scores_df = pd.read_csv(SCORES_PATH)
    print(f"Loaded {len(scores_df)} companies from {SCORES_PATH}")

    sample = select_stratified_sample(scores_df, N_COMPANIES)
    print(f"Selected {len(sample)} companies, stratified across score range "
          f"{sample['transparency_score'].min():.1f} - {sample['transparency_score'].max():.1f}")

    init_db()
    with get_session() as session:
        summaries = []
        csv_rows = []

        for _, row in sample.iterrows():
            company = session.query(Company).filter_by(cin=row["cin"]).first()
            if company is None:
                continue
            filing = get_all_filings(session, company.id)[0]

            text_facts = (
                session.query(Fact)
                .filter(Fact.filing_id == filing.id, Fact.concept.like("%ExplanatoryTextBlock%"))
                .all()
            )

            # Real bug found and fixed here (see conversation history): the
            # original version took the first MAX_SEGMENTS_PER_COMPANY
            # segments in DB query-order, which for companies with 50+
            # total segments (DLF: 69, Zensar: 56, Eureka Forbes: 51)
            # happened to be dominated by bare weblinks/certification
            # lists rather than substantive narrative — giving human raters
            # an unrepresentative, artificially-thin view of those
            # companies' actual disclosure content and producing a
            # misleadingly weak correlation (r=0.30, not significant) that
            # reflected a sampling artifact rather than the Transparency
            # Score's real validity. Fixed by (1) excluding bare-URL
            # segments explicitly and (2) sampling randomly rather than
            # taking the first N in query-order.
            import random as _random
            rng = _random.Random(hash(row["cin"]) % (2**32))  # deterministic per-company, reproducible

            seen = set()
            candidates = []
            for f in text_facts:
                text = f.value.strip()
                if len(text) < MIN_TEXT_LENGTH or text in seen:
                    continue
                if text.strip().lower().startswith(("http://", "https://")):
                    continue
                seen.add(text)
                candidates.append(text)

            rng.shuffle(candidates)
            segments = candidates[:MAX_SEGMENTS_PER_COMPANY]

            summaries.append(f"{'='*80}\nCOMPANY: {company.name}\n{'='*80}\n")
            for i, seg in enumerate(segments, 1):
                summaries.append(f"[Segment {i}]\n{seg}\n")
            summaries.append("\n")

            csv_rows.append({
                "company_name": company.name,
                "cin": company.cin,
                "ai_transparency_score": row["transparency_score"],  # kept for later comparison, NOT shown to the rater during scoring
                "human_score": "",
            })

    OUTPUT_SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_SUMMARY_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(summaries))

    with open(OUTPUT_CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["company_name", "cin", "ai_transparency_score", "human_score"])
        writer.writeheader()
        writer.writerows(csv_rows)

    print(f"\nReadable summaries written to {OUTPUT_SUMMARY_PATH}")
    print(f"Scoring CSV (fill in human_score column) written to {OUTPUT_CSV_PATH}")
    print("\nIMPORTANT: read the summaries WITHOUT looking at ai_transparency_score "
          "in the CSV while scoring, to avoid anchoring bias.")


if __name__ == "__main__":
    main()
