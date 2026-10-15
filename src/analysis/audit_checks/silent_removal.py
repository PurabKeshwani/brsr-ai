"""
Silent Removal Detector

Checks whether a concept that was disclosed with a value in the PREVIOUS
financial year's own comparative data (which BRSR filings include within
the SAME XBRL document, via *_PY context suffixes) has NO current-year
value at all. A company reporting a bad number one year and then omitting
that same metric's current-year disclosure the next year is a distinct,
worth-flagging pattern from simply having a negative trend — it's an
absence, not a decline, and absences don't get caught by trend analysis
(which requires both a current AND prior value to compute anything).

Framing: an absence is not automatically "hiding bad news" — a metric can
legitimately become inapplicable (e.g. Zero Liquid Discharge no longer
relevant after a facility closure) or a company might disclose it via a
differently-named concept in a schema update. This module flags absences
for review with the prior-year value shown, not a verdict.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from db.models import Fact


@dataclass
class SilentRemovalFlag:
    concept: str
    dimensions_key: str
    prior_year_value: str
    prior_year_period: str
    rationale: str


def _dims_key(dims: dict) -> str:
    items = sorted(dims.items())
    return " | ".join(f"{k}={v}" for k, v in items) or "(no dimensions)"


def find_silently_removed_metrics(session: Session, filing_id: int) -> list[SilentRemovalFlag]:
    """Compares concepts present with a PY (previous-year) period against
    the same concept+dimensions in the current period. Flags any that
    appear in the prior period but have no matching current-period fact.
    """
    facts = session.query(Fact).filter_by(filing_id=filing_id).all()

    # Group by (concept, non-period dimensions) -> {period_label: fact}
    groups: dict[tuple[str, str], dict[str, Fact]] = {}
    for f in facts:
        key = (f.concept, _dims_key(f.dimensions))
        period_label = f.period_instant or f.period_end or "unknown"
        groups.setdefault(key, {})[period_label] = f

    # Determine the two most recent distinct periods seen anywhere in this
    # filing, so we compare like-for-like without hardcoding date strings.
    all_periods = sorted({p for g in groups.values() for p in g.keys()})
    if len(all_periods) < 2:
        return []  # can't compare — only one period present anywhere
    latest_period, prior_period = all_periods[-1], all_periods[-2]

    flags = []
    for (concept, dims_key), by_period in groups.items():
        if prior_period not in by_period:
            continue  # nothing to compare — wasn't disclosed before either
        if latest_period in by_period:
            continue  # present in both — no removal

        prior_fact = by_period[prior_period]
        if not prior_fact.value or prior_fact.value.strip() in ("", "NA", "N/A", "0"):
            continue  # prior value itself was empty/zero — not a meaningful removal

        flags.append(SilentRemovalFlag(
            concept=concept,
            dimensions_key=dims_key,
            prior_year_value=prior_fact.value,
            prior_year_period=prior_period,
            rationale=(
                f"Concept '{concept}' (context: {dims_key}) had value "
                f"'{prior_fact.value}' in period {prior_period}, but has no "
                f"corresponding disclosure in the current period ({latest_period}). "
                f"This may be a legitimate change in applicability — worth confirming "
                f"against the filing's own notes before treating as a concern."
            ),
        ))
    return flags