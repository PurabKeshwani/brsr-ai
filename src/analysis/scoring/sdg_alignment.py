"""
Transparency Score — SDG Alignment Component (Phase E3)

Maps each SEBI BRSR Principle (P1-P9) to the UN Sustainable Development
Goals it primarily addresses, per standard ESG-to-SDG correspondence used
in sustainability literature (see GRI Standards' own SDG mapping guidance,
and the report's own partial mapping in section 3.6, extended here to
cover all 9 principles rather than the 5 originally listed).

A company's SDG Alignment score is the fraction of UN SDGs (out of 17)
for which the company has at least one non-trivial PrincipleAxis-labeled
disclosure under a principle mapped to that SDG — i.e. this measures
BREADTH of SDG coverage implied by which principles a company actually
discloses on, not a claim-level SDG-text-mining exercise (which BRSR does
not require and this project has no ground truth for).

This is a coarser measure than the report's stated per-target (169
targets) SDG mapping — deliberately so, since a target-level mapping
would require expert curation this project does not have. Disclosed
honestly as a principle-to-goal correspondence, not textual SDG mention
detection.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from db.models import Fact, Filing

# Principle -> set of UN SDG numbers it primarily addresses. Compiled from
# standard ESG/SDG correspondence guidance (GRI's SDG mapping service) and
# the report's own stated mappings (3.6) for P2, P3, P8, P13(sic->P6/16/17
# in the report's text), extended to cover P1, P4, P5, P7, P9 using the
# same standard-correspondence sources.
PRINCIPLE_TO_SDGS: dict[int, set[int]] = {
    1: {16},                    # Ethics, Transparency, Governance -> Peace, Justice, Strong Institutions
    2: {12, 9},                 # Sustainable Goods & Services -> Responsible Consumption, Industry/Innovation
    3: {8, 3, 5},                # Employee Wellbeing -> Decent Work, Good Health, Gender Equality
    4: {17, 10},                 # Stakeholder Engagement -> Partnerships, Reduced Inequality
    5: {10, 8, 16},              # Human Rights -> Reduced Inequality, Decent Work, Strong Institutions
    6: {13, 6, 7, 12, 15},        # Environmental Stewardship -> Climate Action, Water, Energy, Consumption, Life on Land
    7: {16, 17},                 # Public Policy Advocacy -> Strong Institutions, Partnerships
    8: {1, 8, 10, 11},            # Inclusive Growth -> No Poverty, Decent Work, Reduced Inequality, Sustainable Cities
    9: {12, 9},                  # Consumer Value & Safety -> Responsible Consumption, Industry/Innovation
}

TOTAL_SDGS = 17

PRINCIPLE_TO_LABEL = {f"Principle{i}Member": i for i in range(1, 10)}
MIN_TEXT_LENGTH = 20


@dataclass
class SDGAlignmentResult:
    principles_disclosed: set[int]
    sdgs_covered: set[int]
    sdg_alignment_pct: float


def get_sdg_alignment_score(session: Session, filing_id: int) -> SDGAlignmentResult:
    """
    A principle counts toward SDG coverage only if it has at least one
    SUBSTANTIVE disclosure — defined as containing a KPI/numeric entity
    (reusing analysis/vagueness_lexicon.py's has_kpi check) — not merely
    "some text was filed under this principle."

    Real design flaw found and fixed here (see conversation history):
    the original version counted a principle as "disclosed" if ANY
    non-trivial text existed under it. Since all 9 principles are SEBI-
    mandatory and every ingested company files something under all of
    them, that made the SDG Alignment score identical (82.35%) across
    every company regardless of actual disclosure quality — a
    non-discriminating, effectively dead component contributing pure
    noise to the composite Transparency Score. Requiring at least one
    KPI-backed segment per principle ties this component to genuine
    disclosure depth instead of mere presence.
    """
    from analysis.vagueness.vagueness_lexicon import analyze_vagueness

    text_facts = (
        session.query(Fact)
        .filter(Fact.filing_id == filing_id, Fact.concept.like("%ExplanatoryTextBlock%"))
        .all()
    )

    # Deduplicate (concept, text) per principle, same rationale as
    # specificity_clarity_score.py and build_training_dataset.py.
    seen: dict[tuple[str, str], tuple[int, str]] = {}
    for f in text_facts:
        principle_dim = f.dimensions.get("PrincipleAxis")
        text = f.value.strip()
        if principle_dim in PRINCIPLE_TO_LABEL and len(text) >= MIN_TEXT_LENGTH:
            seen[(f.concept, text)] = (PRINCIPLE_TO_LABEL[principle_dim], text)

    principles_disclosed: set[int] = set()
    for principle_num, text in seen.values():
        if analyze_vagueness(text).has_kpi:
            principles_disclosed.add(principle_num)

    sdgs_covered: set[int] = set()
    for principle_num in principles_disclosed:
        sdgs_covered |= PRINCIPLE_TO_SDGS.get(principle_num, set())

    pct = round(len(sdgs_covered) / TOTAL_SDGS * 100, 2)

    return SDGAlignmentResult(
        principles_disclosed=principles_disclosed,
        sdgs_covered=sdgs_covered,
        sdg_alignment_pct=pct,
    )