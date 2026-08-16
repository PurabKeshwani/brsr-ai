"""
Transparency Score — Completeness Component (Phase E1)

Report's stated formula (4.9.3): C = (Answered Questions / 140) × 100,
where "140" was the report's count of SEBI's mandatory BRSR questions
from a source we do not have (no canonical list of 140 concept-names was
available to this project). Instead of guessing that number, this module
derives its own denominator directly from the data: the union of all
distinct XBRL concepts observed across every ingested filing in the
database. Since every BRSR filer uses the same SEBI-mandated taxonomy,
this union approximates "the full set of concepts a maximally complete
filing could report" — a company's completeness is then the fraction of
that universe it actually filed with a non-trivial value.

This is a deliberate methodological substitution, to be described
honestly in the paper as data-derived rather than sourced from SEBI's
official question count. It is corpus-size-dependent (grows as more
companies are ingested) — see get_completeness_score's docstring for the
practical implication of that.

"Non-trivial" follows the report's own definition (4.9.3): a response
with fewer than 10 words, or a bare NA/blank, doesn't count as answered
— this stops a company from inflating its score by filing a field with a
placeholder value.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from db.models import Fact, Filing

# "0" was previously included here on the assumption it always means
# "no answer" — WRONG, confirmed by real data (see conversation history):
# NumberOfEmployeesOrWorkersIncludingDifferentlyAbled = '0' is a genuine,
# meaningful disclosure ("this company reports zero differently-abled
# employees"), not an unanswered field. Removed from this set; "0" is now
# only treated as trivial if the concept is a narrative/text field, not a
# numeric one (see _is_non_trivial).
TRIVIAL_VALUES = {"", "na", "n/a", "none", "nil", "-", "not applicable"}
MIN_TEXT_WORDS_FOR_NON_TRIVIAL = 10  # matches the report's own stated threshold (4.9.3)


def _is_non_trivial(concept: str, value: str) -> bool:
    """
    Two real bugs fixed here (found against real Aditya Vision Limited
    data — see conversation history):

    1. The word-count threshold was applied to ANY string over 30 chars
       with a space, which incorrectly marked a complete, valid address
       ('ADITYA HOUSE, M-20, ROAD NO. 26, S.K. NAGAR, PATNA-800001(BIHAR)')
       as trivial — it has only 9 whitespace-split "words" despite being
       a full, specific address. The word-count check is now scoped to
       ONLY apply to genuine narrative concepts (ExplanatoryTextBlock),
       matching what it was actually designed for.
    2. "0" was blanket-treated as a non-answer, which incorrectly
       discarded genuine numeric disclosures of zero (e.g. a company
       correctly reporting zero differently-abled employees). "0" is
       only trivial for narrative concepts now (an empty/placeholder
       text block), not for structured numeric/Yes-No/date fields.
    """
    stripped = value.strip()
    if not stripped:
        return False

    is_narrative_concept = "ExplanatoryTextBlock" in concept

    if is_narrative_concept:
        if stripped.lower() in TRIVIAL_VALUES or stripped == "0":
            return False
        if len(stripped) > 30:
            return len(stripped.split()) >= MIN_TEXT_WORDS_FOR_NON_TRIVIAL
        return True

    # Structured (non-narrative) field: any value that isn't an explicit
    # non-answer marker counts, including "0" and short strings.
    return stripped.lower() not in TRIVIAL_VALUES


@dataclass
class CompletenessResult:
    filed_concept_count: int
    universe_size: int
    completeness_pct: float
    missing_concepts: list[str]  # concepts present in the universe but absent (or trivial) in this filing


def get_concept_universe(session: Session) -> set[str]:
    """The denominator: every distinct concept name observed across ALL
    ingested filings in the database. Grows as more companies are
    ingested — see module docstring."""
    rows = session.query(Fact.concept).distinct().all()
    return {r[0] for r in rows}


def get_completeness_score(session: Session, filing_id: int, universe: set[str] | None = None) -> CompletenessResult:
    """Computes completeness for one filing. Pass a pre-computed
    `universe` when scoring many filings in a loop, to avoid re-querying
    the full distinct-concept set on every call."""
    if universe is None:
        universe = get_concept_universe(session)

    facts = session.query(Fact).filter_by(filing_id=filing_id).all()

    filed_concepts: set[str] = set()
    for f in facts:
        if _is_non_trivial(f.concept, f.value):
            filed_concepts.add(f.concept)

    missing = sorted(universe - filed_concepts)
    pct = round(len(filed_concepts) / len(universe) * 100, 2) if universe else 0.0

    return CompletenessResult(
        filed_concept_count=len(filed_concepts),
        universe_size=len(universe),
        completeness_pct=pct,
        missing_concepts=missing,
    )