"""
Data Access Layer — converts raw Fact rows into clean, typed structures.

Design rationale
-----------------
Raw Fact rows carry XBRL's verbose concept names and string-typed values
(e.g. concept="NumberOfEmployeesOrWorkersIncludingDifferentlyAbled",
value="1282", dimensions={"GenderAxis": "MaleMember", ...}). Nothing above
this layer — analysis engine, frontend, chatbot — should ever touch a raw
Fact or a concept string directly. This module is the single place that
knows XBRL concept names; everything downstream works with named,
type-converted Python objects instead.

This mirrors the same principle held throughout the project: numbers are
never reinterpreted at the extraction layer (xbrl_parser.py stores raw
strings), but a clearly-scoped translation layer converts them exactly
once here, with the conversion logic visible and testable in one place.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from db.models import Company, Fact, Filing


def to_number(value: str) -> Optional[float]:
    """Converts a raw XBRL fact value to a float. Returns None for
    non-numeric or missing values — callers must handle None explicitly
    rather than assuming every fact converts cleanly (some BRSR fields are
    legitimately text, e.g. 'Yes'/'No' fields share concept-name patterns
    with numeric ones in places)."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@dataclass
class GenderSplit:
    """Total/Male/Female/Other breakdown for a single BRSR metric —
    the most common shape in BRSR employee/worker disclosures."""
    total: Optional[float]
    male: Optional[float]
    female: Optional[float]
    other: Optional[float]

    @property
    def female_pct(self) -> Optional[float]:
        if self.total is None or self.female is None or self.total == 0:
            return None
        return round(self.female / self.total * 100, 2)


@dataclass
class YearFact:
    """A single named metric for one filing, with raw value preserved."""
    concept: str
    value_raw: str
    value_numeric: Optional[float]
    unit: Optional[str]
    dimensions: dict


def get_company(session: Session, cin: str) -> Optional[Company]:
    return session.query(Company).filter_by(cin=cin).one_or_none()


def get_company_by_name(session: Session, name_contains: str) -> Optional[Company]:
    """Case-insensitive partial match — convenience for CLI/notebook use.
    Production code (API/frontend) should key on CIN, which is unique and
    stable, not on name matching."""
    return (
        session.query(Company)
        .filter(Company.name.ilike(f"%{name_contains}%"))
        .first()
    )


def get_latest_filing(session: Session, company_id: int) -> Optional[Filing]:
    return (
        session.query(Filing)
        .filter_by(company_id=company_id)
        .order_by(Filing.financial_year_end.desc())
        .first()
    )


def get_all_filings(session: Session, company_id: int) -> list[Filing]:
    return (
        session.query(Filing)
        .filter_by(company_id=company_id)
        .order_by(Filing.financial_year_end.desc())
        .all()
    )


def get_facts_by_concept(session: Session, filing_id: int, concept: str) -> list[Fact]:
    """Returns ALL facts for a concept (there can be several — one per
    dimension combination, e.g. one per gender/category). Callers that
    expect exactly one fact (company-identity fields) should use
    get_single_fact instead and treat >1 result as a data-quality signal,
    not silently take the first one."""
    return session.query(Fact).filter_by(filing_id=filing_id, concept=concept).all()


def get_single_fact(session: Session, filing_id: int, concept: str) -> Optional[YearFact]:
    """For concepts that are filed exactly once per filing with no
    dimensions (e.g. company name, total revenue). Raises if more than one
    match is found, rather than silently picking one — an unexpected
    multi-match here means either the concept isn't actually singular in
    this filing, or a dimension needs to be specified, and both deserve
    investigation rather than a silent guess."""
    facts = get_facts_by_concept(session, filing_id, concept)
    if len(facts) > 1:
        raise ValueError(
            f"Expected exactly one fact for concept={concept!r} in filing_id={filing_id}, "
            f"found {len(facts)}. This concept may require a dimension filter — "
            f"use get_facts_by_concept and filter by dimensions instead."
        )
    if not facts:
        return None
    f = facts[0]
    return YearFact(
        concept=f.concept, value_raw=f.value, value_numeric=to_number(f.value),
        unit=f.unit, dimensions=f.dimensions,
    )


def get_gender_split(
    session: Session, filing_id: int, concept: str, category_axis: str, category_member: str,
) -> GenderSplit:
    """Extracts a Total/Male/Female/Other breakdown for one concept, filtered
    to one category (e.g. category_axis='DetailsOfEmployeesAndWorkersIncludingDifferentlyAbledAxis',
    category_member='PermanentEmployeesMember'). This is the shape verified
    against real NIIT data: dims={'GenderAxis': 'MaleMember', category_axis: category_member}.
    """
    facts = get_facts_by_concept(session, filing_id, concept)
    by_gender: dict[str, float | None] = {}
    for f in facts:
        if f.dimensions.get(category_axis) != category_member:
            continue
        gender = f.dimensions.get("GenderAxis")
        if gender:
            by_gender[gender] = to_number(f.value)

    return GenderSplit(
        total=by_gender.get("GenderMember"),  # the unqualified "all genders" member
        male=by_gender.get("MaleMember"),
        female=by_gender.get("FemaleMember"),
        other=by_gender.get("OtherGenderMember"),
    )