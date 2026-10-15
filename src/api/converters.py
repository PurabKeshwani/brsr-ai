"""
Converts internal dataclasses/ORM objects (from db/, analysis/) into the
API's Pydantic response models — the one place where that translation
happens, kept separate from the route handlers for testability.
"""
from __future__ import annotations

from analysis.audit_checks.assurance import AssuranceProfile
from analysis.audit_checks.consistency import CheckStatus, ConsistencyResult
from analysis.audit_checks.greenwashing import GreenwashingSignal
from analysis.audit_checks.silent_removal import SilentRemovalFlag
from analysis.core.trends import TrendResult
from api.schemas import (
    AssuranceSummary,
    ConsistencyCheckItem,
    ConsistencySummary,
    GreenwashingSignalItem,
    MetricTrend,
    SilentRemovalItem,
    TrendPoint,
)

from api.schemas import TransparencyScoreBreakdown


def trend_to_schema(trend: TrendResult) -> MetricTrend:
    return MetricTrend(
        concept=trend.concept,
        series=[TrendPoint(period=yv.period_label, value=yv.value) for yv in trend.series],
        latest_value=trend.latest_value,
        previous_value=trend.previous_value,
        yoy_change_pct=trend.yoy_change_pct,
        direction=trend.direction,
    )


def consistency_to_schema(results: list[ConsistencyResult]) -> ConsistencySummary:
    passed = sum(1 for r in results if r.status == CheckStatus.PASS)
    failed_results = [r for r in results if r.status == CheckStatus.FAIL]
    skipped = sum(1 for r in results if r.status == CheckStatus.SKIP)
    return ConsistencySummary(
        total_checks=len(results),
        passed=passed,
        failed=len(failed_results),
        skipped=skipped,
        failures=[
            ConsistencyCheckItem(concept=r.concept, context=r.context_key, status=r.status.value, message=r.message)
            for r in failed_results
        ],
    )


def assurance_to_schema(profile: AssuranceProfile) -> AssuranceSummary:
    return AssuranceSummary(
        total_disclosure_areas=profile.total_disclosure_areas,
        assured_count=profile.assured_count,
        reasonable_count=profile.reasonable_count,
        limited_count=profile.limited_count,
        unassured_count=profile.unassured_count,
        reasonable_assurance_pct=profile.reasonable_assurance_pct,
        low_assurance_areas=profile.low_assurance_areas(),
    )


def greenwashing_signal_to_schema(signal: GreenwashingSignal) -> GreenwashingSignalItem:
    return GreenwashingSignalItem(
        concept=signal.concept,
        severity=signal.severity.value,
        matched_sentence=signal.matched_sentence,
        previous_value=signal.trend.previous_value,
        latest_value=signal.trend.latest_value,
        yoy_change_pct=signal.trend.yoy_change_pct,
        assurance_level=signal.assurance_level,
        rationale=signal.rationale,
    )


def silent_removal_to_schema(flag: SilentRemovalFlag) -> SilentRemovalItem:
    return SilentRemovalItem(
        concept=flag.concept,
        context=flag.dimensions_key,
        prior_year_value=flag.prior_year_value,
        prior_year_period=flag.prior_year_period,
        rationale=flag.rationale,
    )

def transparency_score_to_schema(result) -> TransparencyScoreBreakdown:
    return TransparencyScoreBreakdown(
        completeness_pct=result.completeness.completeness_pct,
        specificity_pct=result.specificity_clarity.specificity_pct,
        clarity_pct=result.specificity_clarity.clarity_pct,
        sdg_alignment_pct=result.sdg.sdg_alignment_pct,
        composite_score=result.composite_score,
    )