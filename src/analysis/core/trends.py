"""
Multi-Year Trend Extraction

A single BRSR XBRL filing carries facts for MULTIPLE periods within one
document — current FY (context suffix/id like DCYMain), previous FY
(DPYMain / *_PY), and for some concepts (e.g. TurnoverRate) even the year
before that (*_PPY). This means trend analysis doesn't need multiple
ingested filings — it can be computed from a single filing's facts by
grouping on period_end and sorting chronologically.

Verified against real NIIT data: TotalScope1Emissions has exactly two
periods in one filing (FY2025-26: 870.29, FY2024-25: 290.06).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from analysis.core.queries import to_number
from db.models import Fact


@dataclass
class YearValue:
    period_end: Optional[str]
    period_instant: Optional[str]
    value: float

    @property
    def period_label(self) -> str:
        return self.period_instant or self.period_end or "unknown"


def _dimensions_match(fact_dims: dict, filter_dims: dict) -> bool:
    return all(fact_dims.get(k) == v for k, v in filter_dims.items())


def get_multi_year_series(
    session: Session, filing_id: int, concept: str, dimension_filter: Optional[dict] = None,
) -> list[YearValue]:
    """Returns every numeric value for a concept across all periods present
    in this filing, sorted chronologically (oldest first). If
    dimension_filter is given, only facts whose dimensions match ALL
    given key-value pairs are included (other dimensions on the fact are
    ignored, allowing partial filters).
    """
    facts = session.query(Fact).filter_by(filing_id=filing_id, concept=concept).all()
    if dimension_filter:
        facts = [f for f in facts if _dimensions_match(f.dimensions, dimension_filter)]

    results = []
    for f in facts:
        value = to_number(f.value)
        if value is None:
            continue
        results.append(YearValue(period_end=f.period_end, period_instant=f.period_instant, value=value))

    results.sort(key=lambda yv: yv.period_label)
    return results


@dataclass
class TrendResult:
    concept: str
    series: list[YearValue]

    @property
    def latest_value(self) -> Optional[float]:
        return self.series[-1].value if self.series else None

    @property
    def previous_value(self) -> Optional[float]:
        return self.series[-2].value if len(self.series) >= 2 else None

    @property
    def yoy_change_pct(self) -> Optional[float]:
        """Percentage change from the second-most-recent to the most recent
        period. None if fewer than 2 periods are available — callers must
        handle this explicitly rather than assume a trend exists."""
        if self.previous_value is None or self.latest_value is None or self.previous_value == 0:
            return None
        return round((self.latest_value - self.previous_value) / abs(self.previous_value) * 100, 2)

    @property
    def direction(self) -> str:
        change = self.yoy_change_pct
        if change is None:
            return "insufficient_data"
        if change > 0.5:
            return "increased"
        if change < -0.5:
            return "decreased"
        return "flat"


def get_trend(
    session: Session, filing_id: int, concept: str, dimension_filter: Optional[dict] = None,
) -> TrendResult:
    series = get_multi_year_series(session, filing_id, concept, dimension_filter)
    return TrendResult(concept=concept, series=series)