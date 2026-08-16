"""
Greenwashing Signal Layer

CRITICAL FRAMING: A contradiction between a narrative claim and the
underlying numeric trend is EVIDENCE worth surfacing for human review —
NOT proof of greenwashing. This module finds and explains tension between
claim and evidence; judging intent is explicitly out of scope.

BUGS FIXED HERE, FOUND AGAINST REAL NIIT DATA:
1. Sentence-level matching (not paragraph-level): NIIT's real GHG narrative
   text contains "Scope 1 emissions are increase..." (an honest admission,
   NOT a claim of improvement) in the SAME paragraph as "Scope 2 Grid
   electricity consumption is reduced by approx. 5.00%..." (a genuine
   Scope-2 claim). Paragraph-level matching incorrectly attached the
   Scope-2 improvement claim to Scope 1. Fixed by splitting into sentences
   and requiring both the improvement phrase AND the concept-specific
   phrase to co-occur in the SAME sentence.
2. Assurance topic name mismatch: numeric fact concepts (e.g.
   "TotalScope1Emissions") don't share a name with their assurance tag's
   topic (e.g. "WhetherDetailsOfGreenHouseGasEmissionsAndItsIntensityIsAssuredByAssurer").
   Fixed with an explicit, verified-against-real-XBRL mapping — see
   ASSURANCE_TOPIC_BY_CONCEPT.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from sqlalchemy.orm import Session

from analysis.assurance import get_assurance_profile
from analysis.trends import TrendResult, get_trend
from db.models import Fact

# Allows arbitrary words between the verb and "by" (e.g. "reduced OUR
# EMISSIONS by 20%"), not just directly-adjacent phrasing ("reduced by
# 20%"). Found as a real gap via synthetic testing: NIIT's actual text
# happened to use tight "reduced by X%" phrasing which passed the old
# strict pattern, but "reduced [object] by X%" — an equally common and
# realistic phrasing — was silently missed. Scoped to a single sentence
# (this always runs after _split_sentences), so ".*" here can't spill
# across unrelated sentences.
IMPROVEMENT_PHRASES = [
    r"reduc\w+.*\bby\b",
    r"decreas\w+.*\bby\b",
    r"improv\w+",
    r"lower\w*.*(?:than|compared)",
    r"declin\w+.*\bby\b",
    r"cut.*(?:\bby\b|\bdown\b)",
]

CLAIM_RELEVANT_CONCEPTS: dict[str, list[str]] = {
    "TotalScope1Emissions": [r"scope\s*1\b"],
    "TotalScope2Emissions": [r"scope\s*2\b"],
    "TotalScope3Emissions": [r"scope\s*3\b"],
    "TotalWasteGenerated": [r"\bwaste\b"],
    "TotalVolumeOfWaterWithdrawal": [r"\bwater\b"],
    "TotalEnergyConsumedFromNonRenewableSources": [r"non-?renewable", r"\benergy\b"],
}

# Maps each tracked numeric concept to the "topic" name used in that
# concept's own assurance tags, verified directly against real NIIT XBRL
# (e.g. "WhetherDetailsOfGreenHouseGasEmissionsAndItsIntensityIsAssuredByAssurer"
# = true, "AssuranceSubTypeForDetailsOfGreenHouseGasEmissionsAndItsIntensity"
# = "Reasonable"). Do not assume this mapping generalizes to other filers
# without re-verifying — SEBI's taxonomy is standard, but confirm before
# trusting on a new company.
ASSURANCE_TOPIC_BY_CONCEPT = {
    "TotalScope1Emissions": "DetailsOfGreenHouseGasEmissionsAndItsIntensity",
    "TotalScope2Emissions": "DetailsOfGreenHouseGasEmissionsAndItsIntensity",
    "TotalScope3Emissions": "DetailsOfTotalScope3EmissionsAndItsIntensity",
    "TotalWasteGenerated": "DetailsRelatedToWasteManagementByTheEntity",
    "TotalVolumeOfWaterWithdrawal": "DetailsOfTheDisclosuresRelatedToWaterWithdrawal",
    "TotalEnergyConsumedFromNonRenewableSources": "DetailsOfTotalEnergyConsumptionInJoulesOrMultiplesAndEnergyIntensity",
}


class Severity(Enum):
    INFO = "info"
    WORTH_REVIEWING = "worth_reviewing"
    NOTABLE = "notable"


@dataclass
class GreenwashingSignal:
    concept: str
    narrative_source_concept: str
    matched_sentence: str  # the specific sentence, not the whole paragraph
    trend: TrendResult
    severity: Severity
    rationale: str
    is_assured: bool
    assurance_level: str | None
    matched_in_n_locations: int


def _get_narrative_facts(session: Session, filing_id: int) -> list[Fact]:
    return (
        session.query(Fact)
        .filter(Fact.filing_id == filing_id, Fact.concept.like("%ExplanatoryTextBlock%"))
        .all()
    )


def _deduplicate_narrative_texts(facts: list[Fact]) -> list[tuple[str, str, int]]:
    seen: dict[str, tuple[str, int]] = {}
    for f in facts:
        text = f.value.strip()
        if not text:
            continue
        if text in seen:
            concept, count = seen[text]
            seen[text] = (concept, count + 1)
        else:
            seen[text] = (f.concept, 1)
    return [(concept, text, count) for text, (concept, count) in seen.items()]


def _split_sentences(text: str) -> list[str]:
    """Splits on sentence-ending punctuation and newlines. Deliberately
    simple (BRSR prose is straightforward) — good enough to separate
    "Scope 1 emissions increased..." from "Scope 2 ... reduced by 5%" when
    they appear back-to-back in one paragraph, which is the real case that
    motivated this fix."""
    raw = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [s.strip() for s in raw if s.strip()]


def _text_claims_improvement(text: str) -> bool:
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in IMPROVEMENT_PHRASES)


def _text_matches_concept(concept: str, text: str) -> bool:
    patterns = CLAIM_RELEVANT_CONCEPTS.get(concept, [])
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


def _get_assurance(concept: str, assurance_by_topic: dict) -> tuple[bool, str | None]:
    topic = ASSURANCE_TOPIC_BY_CONCEPT.get(concept)
    if not topic or topic not in assurance_by_topic:
        return False, None
    item = assurance_by_topic[topic]
    return item.is_assured, item.assurance_level


def find_claim_evidence_signals(session: Session, filing_id: int) -> list[GreenwashingSignal]:
    narrative_facts = _get_narrative_facts(session, filing_id)
    deduplicated = _deduplicate_narrative_texts(narrative_facts)

    assurance = get_assurance_profile(session, filing_id)
    assurance_by_topic = {item.disclosure_area: item for item in assurance.items}

    signals: list[GreenwashingSignal] = []
    seen_signal_keys: set[tuple[str, str]] = set()

    for concept in CLAIM_RELEVANT_CONCEPTS:
        trend = get_trend(session, filing_id, concept)
        if trend.direction != "increased":
            continue

        for narrative_concept, text, occurrence_count in deduplicated:
            for sentence in _split_sentences(text):
                if not _text_claims_improvement(sentence):
                    continue
                if not _text_matches_concept(concept, sentence):
                    continue

                key = (concept, sentence)
                if key in seen_signal_keys:
                    continue
                seen_signal_keys.add(key)

                is_assured, assurance_level = _get_assurance(concept, assurance_by_topic)
                severity = Severity.NOTABLE if assurance_level != "Reasonable" else Severity.WORTH_REVIEWING

                signals.append(GreenwashingSignal(
                    concept=concept,
                    narrative_source_concept=narrative_concept,
                    matched_sentence=sentence,
                    trend=trend,
                    severity=severity,
                    rationale=(
                        f"Sentence contains improvement language and specifically references "
                        f"{concept}, but the filed numeric trend shows a {trend.yoy_change_pct}% "
                        f"INCREASE ({trend.previous_value} -> {trend.latest_value}) — opposite to "
                        f"what this sentence suggests. Source paragraph appears {occurrence_count} "
                        f"time(s) in the filing. Assurance level: {assurance_level or 'not assured'}."
                    ),
                    is_assured=is_assured,
                    assurance_level=assurance_level,
                    matched_in_n_locations=occurrence_count,
                ))

    return signals