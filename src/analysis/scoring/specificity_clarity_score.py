"""
Transparency Score — Specificity and Clarity Components (Phase E2)

Both components reuse the vagueness-detection infrastructure already
built and validated in Phase D (see analysis/vagueness_lexicon.py,
vagueness_combined.py) rather than duplicating logic — Specificity is
the KPI-presence rate, Clarity is the inverse of the vague-flag rate,
computed over the same deduplicated narrative-text set.

Report's stated formulas (4.9.3):
  Specificity: Sp = min((Total KPI Entities / (Total Segments × 2.0)), 1.0) × 100
  Clarity: Cl = max((1 − (Flagged Segments / Total Segments)), 0) × 100

We deviate slightly from the Specificity formula: the report counts total
KPI ENTITY occurrences (allowing a segment to contribute more than one),
scaled by an empirically-chosen "2.0 KPIs per segment" denominator we have
no basis to replicate. Instead we use the simpler, more directly
interpretable rate: the fraction of segments that contain AT LEAST ONE
KPI. This is a deliberate, disclosed substitution — described honestly in
the paper as a simplification, not a claim of matching the report's exact
formula.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from analysis.vagueness.vagueness_combined import analyze_combined_vagueness
from analysis.vagueness.vagueness_lexicon import analyze_vagueness
from db.models import Fact

MIN_TEXT_LENGTH = 30


def get_deduplicated_narrative_texts(session: Session, filing_id: int) -> list[str]:
    """Same (concept, text) deduplication as build_training_dataset.py
    and run_combined_vagueness.py — see those modules' docstrings for why
    this is necessary (SEBI's form structure replicates the same
    boilerplate text across multiple PrincipleAxis tags)."""
    text_facts = (
        session.query(Fact)
        .filter(Fact.filing_id == filing_id, Fact.concept.like("%ExplanatoryTextBlock%"))
        .all()
    )
    seen: dict[tuple[str, str], str] = {}
    for f in text_facts:
        text = f.value.strip()
        if len(text) < MIN_TEXT_LENGTH:
            continue
        seen[(f.concept, text)] = text
    return list(seen.values())


@dataclass
class SpecificityClarityResult:
    total_segments: int
    segments_with_kpi: int
    segments_flagged_vague: int
    specificity_pct: float
    clarity_pct: float


def get_specificity_clarity_score(session: Session, filing_id: int) -> SpecificityClarityResult:
    texts = get_deduplicated_narrative_texts(session, filing_id)

    if not texts:
        return SpecificityClarityResult(
            total_segments=0, segments_with_kpi=0, segments_flagged_vague=0,
            specificity_pct=0.0, clarity_pct=0.0,
        )

    segments_with_kpi = 0
    segments_flagged_vague = 0

    for text in texts:
        lexicon_result = analyze_vagueness(text)
        if lexicon_result.has_kpi:
            segments_with_kpi += 1

        combined_result = analyze_combined_vagueness(text)
        if combined_result.is_flagged_vague:
            segments_flagged_vague += 1

    total = len(texts)
    specificity_pct = round(segments_with_kpi / total * 100, 2)
    clarity_pct = round((1 - segments_flagged_vague / total) * 100, 2)

    return SpecificityClarityResult(
        total_segments=total,
        segments_with_kpi=segments_with_kpi,
        segments_flagged_vague=segments_flagged_vague,
        specificity_pct=specificity_pct,
        clarity_pct=clarity_pct,
    )