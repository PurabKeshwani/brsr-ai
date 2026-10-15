"""
Transparency Score — Composite (Phase E, final)

TS = 0.40 x Completeness + 0.30 x Specificity + 0.20 x Clarity + 0.10 x SDGAlignment

Weights match the report's stated formula (4.9.3). Each component's own
module docstring documents where and why this project's implementation
deliberately deviates from the report's exact formula (data-derived
denominators instead of SEBI's official question count, KPI-presence rate
instead of KPI-density-per-segment, principle-to-SDG-goal correspondence
instead of per-target text mining) — those deviations are disclosed there,
not hidden here.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from analysis.scoring.completeness_score import CompletenessResult, get_completeness_score, get_concept_universe
from analysis.scoring.sdg_alignment import SDGAlignmentResult, get_sdg_alignment_score
from analysis.scoring.specificity_clarity_score import SpecificityClarityResult, get_specificity_clarity_score

WEIGHT_COMPLETENESS = 0.40
WEIGHT_SPECIFICITY = 0.30
WEIGHT_CLARITY = 0.20
WEIGHT_SDG = 0.10


@dataclass
class TransparencyScoreResult:
    completeness: CompletenessResult
    specificity_clarity: SpecificityClarityResult
    sdg: SDGAlignmentResult
    composite_score: float


def get_transparency_score(session: Session, filing_id: int, concept_universe: set[str] | None = None) -> TransparencyScoreResult:
    if concept_universe is None:
        concept_universe = get_concept_universe(session)

    completeness = get_completeness_score(session, filing_id, universe=concept_universe)
    spec_clarity = get_specificity_clarity_score(session, filing_id)
    sdg = get_sdg_alignment_score(session, filing_id)

    composite = (
        WEIGHT_COMPLETENESS * completeness.completeness_pct
        + WEIGHT_SPECIFICITY * spec_clarity.specificity_pct
        + WEIGHT_CLARITY * spec_clarity.clarity_pct
        + WEIGHT_SDG * sdg.sdg_alignment_pct
    )

    return TransparencyScoreResult(
        completeness=completeness,
        specificity_clarity=spec_clarity,
        sdg=sdg,
        composite_score=round(composite, 2),
    )