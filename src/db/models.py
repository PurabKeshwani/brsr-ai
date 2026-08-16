"""
BRSR Database Schema

Design rationale
-----------------
- `Fact.value` is ALWAYS stored as the raw string exactly as filed in the
  XBRL — never cast, rounded, or reinterpreted at ingestion time. This
  mirrors the core principle held throughout this project: extraction
  layers never alter numbers, only downstream analysis code (which can be
  tested and audited separately) interprets them.
- `Fact.dimensions` stores the XBRL context's explicit/typed members
  (gender, employee category, benefit type, etc.) as JSON — this is what
  lets us tell apart e.g. "Male, Permanent Employees" from "Female,
  Workers" for the same concept, which was the exact problem that made
  PDF extraction unreliable (merged/ambiguous table headers). In XBRL this
  is unambiguous and explicit, so we just preserve it as-is.
- One row per (filing, concept, context) — a filing is re-ingestable: see
  `ingestion.xbrl_ingest.ingest_filing`, which deletes-then-reinserts a
  filing's facts, making repeated runs safe rather than requiring complex
  fact-level dedup logic.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cin: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    isin: Mapped[str | None] = mapped_column(String(32), nullable=True)
    nse_symbol: Mapped[str | None] = mapped_column(String(32), nullable=True)
    nic_code: Mapped[str | None] = mapped_column(String(16), nullable=True)  # sector classification, from XBRL
    registered_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    filings: Mapped[list["Filing"]] = relationship(back_populates="company", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"Company(cin={self.cin!r}, name={self.name!r})"


class Filing(Base):
    __tablename__ = "filings"
    __table_args__ = (
        UniqueConstraint("company_id", "financial_year_end", name="uq_filing_company_year"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    financial_year_start: Mapped[str] = mapped_column(String(16))  # ISO date, e.g. "2025-04-01"
    financial_year_end: Mapped[str] = mapped_column(String(16))
    xbrl_source_url: Mapped[str] = mapped_column(Text)
    raw_fact_count: Mapped[int] = mapped_column(Integer, default=0)
    ingested_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    company: Mapped["Company"] = relationship(back_populates="filings")
    facts: Mapped[list["Fact"]] = relationship(back_populates="filing", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"Filing(company_id={self.company_id}, fy_end={self.financial_year_end!r})"


class Fact(Base):
    __tablename__ = "facts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    filing_id: Mapped[int] = mapped_column(ForeignKey("filings.id"), index=True)

    concept: Mapped[str] = mapped_column(String(255), index=True)
    value: Mapped[str] = mapped_column(Text)  # raw string, exactly as filed — see module docstring
    unit: Mapped[str | None] = mapped_column(String(64), nullable=True)
    decimals: Mapped[str | None] = mapped_column(String(16), nullable=True)

    period_start: Mapped[str | None] = mapped_column(String(16), nullable=True)
    period_end: Mapped[str | None] = mapped_column(String(16), nullable=True)
    period_instant: Mapped[str | None] = mapped_column(String(16), nullable=True)

    dimensions: Mapped[dict] = mapped_column(JSON, default=dict)  # e.g. {"GenderAxis": "MaleMember", ...}

    filing: Mapped["Filing"] = relationship(back_populates="facts")

    def __repr__(self) -> str:
        return f"Fact(concept={self.concept!r}, value={self.value!r}, dims={self.dimensions})"