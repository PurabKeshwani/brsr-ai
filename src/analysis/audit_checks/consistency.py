"""
Internal Consistency Checks — auto-discovers gender-split facts within a
filing and checks whether Male + Female + Other reconciles to Total, and
(for population-composition concepts only) whether gender percentages
sum to ~100%.

TWO REAL BUGS FOUND AGAINST REAL MASTEK DATA (not NIIT — NIIT's filing
happened not to trigger these):

1. Zero-total false failures: when a category (e.g. "Workers") is
   genuinely empty for a company, Male%/Female% are correctly filed as 0%
   each. Expecting them to sum to ~100% is a divide-by-zero-style
   category error, not a real inconsistency. Fixed by checking the
   corresponding Number concept's total before flagging — if the total is
   zero or absent, this is SKIPPED, not FAILED.

2. Wrong concept semantics: "PercentageOfWellBeingOfEmployeesOrWorkers"
   (and similarly-shaped coverage/compliance-rate concepts) represent
   "% of THIS gender covered by benefit X" — an independent rate per
   gender, NOT a population split. Two genders' coverage rates summing to
   ~200% (both near 100% individually) is completely normal and not an
   inconsistency. The percentage-sum check was being applied to ANY
   concept matching "*Percentage*", which is wrong — only concepts
   verified to represent gender COMPOSITION of a total population belong
   in this check. Fixed with an explicit, evidence-verified allowlist
   instead of substring matching.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from sqlalchemy.orm import Session

from analysis.core.queries import to_number
from db.models import Fact

NUMBER_SUM_TOLERANCE = 0.5
PERCENT_SUM_TOLERANCE = 1.0

# Concepts verified (against real NIIT + Mastek data) to represent gender
# COMPOSITION of a total population — i.e. Male% + Female% + Other% should
# genuinely sum to ~100%. This is deliberately a narrow allowlist, not a
# substring match on "Percentage", because many BRSR percentage concepts
# (coverage rates, compliance rates) represent an independent rate PER
# gender instead, which must never sum to 100% and were producing false
# failures (e.g. two ~99% coverage rates correctly summing to ~198%).
COMPOSITION_PERCENTAGE_CONCEPTS = {
    "PercentageOfEmployeesOrWorkersIncludingDifferentlyAbled",
    "PercentageOfDifferentlyAbledEmployeesOrWorkers",
}


class CheckStatus(Enum):
    PASS = "pass"
    FAIL = "fail"
    SKIP = "skip"


@dataclass
class ConsistencyResult:
    concept: str
    context_key: str
    status: CheckStatus
    message: str
    total: Optional[float] = None
    male: Optional[float] = None
    female: Optional[float] = None
    other: Optional[float] = None


def _non_gender_dims_key(dims: dict) -> str:
    items = sorted((k, v) for k, v in dims.items() if k != "GenderAxis")
    return " | ".join(f"{k}={v}" for k, v in items) or "(no other dimensions)"


def _group_by_concept_and_context(facts: list[Fact]) -> dict[tuple[str, str], dict[str, float]]:
    groups: dict[tuple[str, str], dict[str, float]] = {}
    for f in facts:
        gender = f.dimensions.get("GenderAxis")
        if not gender:
            continue
        value = to_number(f.value)
        if value is None:
            continue
        key = (f.concept, _non_gender_dims_key(f.dimensions))
        groups.setdefault(key, {})[gender] = value
    return groups


def check_gender_number_sums(session: Session, filing_id: int) -> list[ConsistencyResult]:
    facts = (
        session.query(Fact)
        .filter(Fact.filing_id == filing_id, Fact.concept.like("%Number%"))
        .all()
    )
    groups = _group_by_concept_and_context(facts)

    results = []
    for (concept, context_key), by_gender in groups.items():
        total = by_gender.get("GenderMember")
        male = by_gender.get("MaleMember")
        female = by_gender.get("FemaleMember")
        other = by_gender.get("OtherGenderMember", 0.0)

        if total is None or male is None or female is None:
            results.append(ConsistencyResult(
                concept=concept, context_key=context_key, status=CheckStatus.SKIP,
                message="Total, Male, or Female value not present for this concept/context",
                total=total, male=male, female=female, other=other,
            ))
            continue

        computed = male + female + other
        if abs(computed - total) < NUMBER_SUM_TOLERANCE:
            results.append(ConsistencyResult(
                concept=concept, context_key=context_key, status=CheckStatus.PASS,
                message=f"{male} + {female} + {other} = {computed} ≈ {total}",
                total=total, male=male, female=female, other=other,
            ))
        else:
            results.append(ConsistencyResult(
                concept=concept, context_key=context_key, status=CheckStatus.FAIL,
                message=f"{male} + {female} + {other} = {computed}, but filed Total is {total} "
                        f"(difference: {round(computed - total, 2)})",
                total=total, male=male, female=female, other=other,
            ))
    return results


def _lookup_total_number(session: Session, filing_id: int, percentage_concept: str, context_key: str) -> Optional[float]:
    """Derives the corresponding Number concept (e.g. 'PercentageOfX' ->
    'NumberOfX' — a naming pattern verified consistent across real NIIT
    and Mastek XBRL) and looks up its Total (GenderMember) value in the
    same non-gender context, to distinguish 'genuinely zero population'
    from 'real missing/inconsistent data'."""
    if not percentage_concept.startswith("PercentageOf"):
        return None
    number_concept = "NumberOf" + percentage_concept[len("PercentageOf"):]

    facts = session.query(Fact).filter_by(filing_id=filing_id, concept=number_concept).all()
    for f in facts:
        if f.dimensions.get("GenderAxis") != "GenderMember":
            continue
        if _non_gender_dims_key(f.dimensions) != context_key:
            continue
        return to_number(f.value)
    return None


def check_gender_percentage_sums(session: Session, filing_id: int) -> list[ConsistencyResult]:
    facts = (
        session.query(Fact)
        .filter(Fact.filing_id == filing_id, Fact.concept.in_(COMPOSITION_PERCENTAGE_CONCEPTS))
        .all()
    )
    groups = _group_by_concept_and_context(facts)

    results = []
    for (concept, context_key), by_gender in groups.items():
        male = by_gender.get("MaleMember")
        female = by_gender.get("FemaleMember")
        other = by_gender.get("OtherGenderMember", 0.0)

        if male is None or female is None:
            results.append(ConsistencyResult(
                concept=concept, context_key=context_key, status=CheckStatus.SKIP,
                message="Male or Female percentage not present for this concept/context",
                male=male, female=female, other=other,
            ))
            continue

        total_pct = (male + female + other) * 100

        if abs(total_pct) < PERCENT_SUM_TOLERANCE:
            # All-zero percentages: check whether the underlying population
            # is genuinely zero before treating this as a failure.
            total_population = _lookup_total_number(session, filing_id, concept, context_key)
            if total_population is not None and abs(total_population) < NUMBER_SUM_TOLERANCE:
                results.append(ConsistencyResult(
                    concept=concept, context_key=context_key, status=CheckStatus.SKIP,
                    message=f"All percentages are 0% and the underlying total population is "
                            f"also 0 ({total_population}) — this category is genuinely empty for "
                            f"this company, not an inconsistency.",
                    male=male, female=female, other=other,
                ))
                continue

        if abs(total_pct - 100) < PERCENT_SUM_TOLERANCE:
            results.append(ConsistencyResult(
                concept=concept, context_key=context_key, status=CheckStatus.PASS,
                message=f"Percentages sum to {round(total_pct, 2)}%",
                male=male, female=female, other=other,
            ))
        else:
            results.append(ConsistencyResult(
                concept=concept, context_key=context_key, status=CheckStatus.FAIL,
                message=f"Percentages sum to {round(total_pct, 2)}%, expected ~100%",
                male=male, female=female, other=other,
            ))
    return results


def run_all_consistency_checks(session: Session, filing_id: int) -> list[ConsistencyResult]:
    return check_gender_number_sums(session, filing_id) + check_gender_percentage_sums(session, filing_id)