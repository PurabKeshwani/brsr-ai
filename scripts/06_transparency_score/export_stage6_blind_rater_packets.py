"""Export Stage 6 rater-safe packets for 30 new companies and Zensar.

The score-bearing input sheet is private. Raters should receive only the
*_blind.csv, corresponding narrative summary, and instructions. The script
does not run scoring or modify the private score file.
"""
from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parents[2]
SRC = BASE / "src"
sys.path.insert(0, str(SRC))

SCORES_PATH = BASE / "data/analysis/transparency_scores.csv"
PRIVATE_NEW_SAMPLE_PATH = BASE / "data/labeling_sheets/stage6_new_ratings.csv"
OUT_DIR = BASE / "data/labeling_sheets"
URL_RE = re.compile(r"(?:https?://|www\.)\S+", flags=re.IGNORECASE)
MIN_TEXT_LENGTH = 30
MAX_SEGMENTS_PER_COMPANY = 10
ZENSAR_CIN = "L72200PN1963PLC012621"


def stable_seed(cin: str) -> int:
    return int(hashlib.sha256(cin.encode("utf-8")).hexdigest()[:16], 16)


def clean_narrative(text: str) -> str:
    # URLs in BRSR narrative facts often point to external PDFs. Keep any
    # accompanying human-readable wording but never expose/score the URL itself.
    cleaned = URL_RE.sub(" ", text or "")
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip(" \t\r\n-–|;,")


def get_company_segments(session, company):
    from db.models import Fact, Filing

    filing = (
        session.query(Filing)
        .filter_by(company_id=company.id)
        .order_by(Filing.financial_year_end.desc())
        .first()
    )
    if filing is None:
        raise ValueError(f"No filing found for {company.name} ({company.cin})")
    facts = (
        session.query(Fact)
        .filter(Fact.filing_id == filing.id, Fact.concept.like("%ExplanatoryTextBlock%"))
        .all()
    )
    seen: set[str] = set()
    candidates: list[str] = []
    for fact in facts:
        raw_text = (fact.value or "").strip()
        text = clean_narrative(raw_text)
        if len(text) < MIN_TEXT_LENGTH or text.casefold() in seen:
            continue
        # If a fact consisted almost entirely of a URL, removing its links
        # leaves no meaningful summary; do not replace it with a score proxy.
        if URL_RE.search(raw_text) and len(re.sub(r"\W", "", text)) < MIN_TEXT_LENGTH:
            continue
        seen.add(text.casefold())
        candidates.append(text)
    if not candidates:
        raise ValueError(f"No eligible narrative segments after URL filtering for {company.name} ({company.cin})")
    import random
    random.Random(stable_seed(company.cin)).shuffle(candidates)
    return filing, candidates[:MAX_SEGMENTS_PER_COMPANY]


def write_packet(session, companies: list[tuple[int, str, str]], prefix: str) -> tuple[Path, Path]:
    from db.models import Company

    rating_rows = []
    summaries = []
    for rating_id, company_name, cin in companies:
        company = session.query(Company).filter_by(cin=cin).one_or_none()
        if company is None:
            raise ValueError(f"Company CIN from private sample not found in database: {cin}")
        filing, segments = get_company_segments(session, company)
        rating_rows.append({"id": rating_id, "company_name": company.name, "cin": company.cin, "human_score": ""})
        summaries.append(
            f"{'=' * 88}\nID: {rating_id}\nCOMPANY: {company.name}\nCIN: {company.cin}\n"
            f"FINANCIAL YEAR END: {filing.financial_year_end}\n{'=' * 88}\n"
        )
        for index, segment in enumerate(segments, start=1):
            summaries.append(f"[Disclosure segment {index}]\n{segment}\n")
        summaries.append("\n")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = OUT_DIR / f"{prefix}_blind.csv"
    summary_path = OUT_DIR / f"{prefix}_summaries.txt"
    pd.DataFrame(rating_rows).to_csv(csv_path, index=False, encoding="utf-8-sig")
    summary_path.write_text("\n".join(summaries), encoding="utf-8")
    return csv_path, summary_path


def main() -> None:
    from db.session import get_session, init_db
    from db.models import Company

    private_sample = pd.read_csv(PRIVATE_NEW_SAMPLE_PATH, dtype={"cin": "string"})
    scores = pd.read_csv(SCORES_PATH, dtype={"cin": "string"})
    required = {"company_name", "cin", "transparency_score"}
    if not required.issubset(private_sample.columns):
        raise ValueError(f"Private sample must contain: {sorted(required)}")
    if len(private_sample) != 30 or private_sample["cin"].duplicated().any():
        raise ValueError(f"Expected 30 unique new-company rows; found {len(private_sample)}")
    if private_sample["human_score"].fillna("").astype(str).str.strip().ne("").any():
        raise ValueError("The private new-rating sample already contains human scores; refusing to re-export a changed cohort.")

    score_by_cin = scores.set_index("cin")["transparency_score"]
    mismatches = []
    for _, row in private_sample.iterrows():
        current = score_by_cin.get(row["cin"])
        if pd.isna(current) or round(float(current), 2) != round(float(row["transparency_score"]), 2):
            mismatches.append(str(row["cin"]))
    if mismatches:
        raise ValueError(f"Private sample does not match current score table for CINs: {mismatches[:5]}")

    new_companies = [
        (index, str(row["company_name"]), str(row["cin"]))
        for index, (_, row) in enumerate(private_sample.iterrows(), start=1)
    ]
    zensar_score = score_by_cin.get(ZENSAR_CIN)
    if pd.isna(zensar_score):
        raise ValueError(f"Zensar CIN missing from transparency scores: {ZENSAR_CIN}")
    zensar_name = "ZENSAR TECHNOLOGIES LIMITED"

    init_db()
    with get_session() as session:
        zensar = session.query(Company).filter_by(cin=ZENSAR_CIN).one_or_none()
        if zensar is None:
            raise ValueError(f"Zensar company not found for CIN {ZENSAR_CIN}")
        zensar_name = zensar.name
        new_csv, new_summary = write_packet(session, new_companies, "stage6_new_ratings")
        zensar_csv, zensar_summary = write_packet(
            session, [(1, zensar_name, ZENSAR_CIN)], "stage6_zensar_rerating"
        )

    instructions = OUT_DIR / "stage6_blind_rater_instructions.md"
    instructions.write_text(
        "# Stage 6 Blind Transparency Rating Instructions\n\n"
        "Rate each company's disclosure summary from 0 to 100 based only on the narrative provided. "
        "Do not request, search for, or view the company's algorithmic transparency score, component scores, "
        "other raters' judgments, or prior ratings. Rate independently.\n\n"
        "Use the full range consistently: 0 means no meaningful transparency information; 25 means sparse or "
        "mostly generic disclosure; 50 means mixed disclosure with some concrete information; 75 means mostly "
        "specific, understandable disclosure across relevant topics; 100 means exceptionally comprehensive, "
        "specific, and clear disclosure. Judge the substance in the provided text, not company reputation or "
        "whether you can access an external link. A numerical score is required for every ID; flag an item "
        "separately if the text is insufficient to rate.\n\n"
        "Enter only a numeric 0–100 score in `human_score` in the matching blind CSV. Keep the summary and CSV "
        "together, and return the completed CSV without altering `id` or `cin`.\n\n"
        "## Files safe to share with the rater\n\n"
        "- `stage6_new_ratings_blind.csv` and `stage6_new_ratings_summaries.txt` for the 30 new companies.\n"
        "- `stage6_zensar_rerating_blind.csv` and `stage6_zensar_rerating_summaries.txt` for the fresh Zensar rating.\n"
        "- This instruction file.\n\n"
        "Never share `stage6_new_ratings.csv` or `data/analysis/transparency_scores.csv`; they contain model scores.\n",
        encoding="utf-8",
    )
    print("Created blind Stage 6 rating packets (no model scores in rater-facing files).")
    print(f"30-company blind sheet: {new_csv}")
    print(f"30-company narratives: {new_summary}")
    print(f"Zensar blind sheet: {zensar_csv}")
    print(f"Corrected Zensar narrative: {zensar_summary}")
    print(f"Instructions: {instructions}")
    print("PRIVATE ONLY — do not give the score-bearing stage6_new_ratings.csv or transparency_scores.csv to raters.")


if __name__ == "__main__":
    main()
