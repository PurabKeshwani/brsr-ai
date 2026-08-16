"""
BRSR Field Mapper — Phase 2 (registry-driven, 3-tier context matching)

Maps a DataRow's positional values to named fields, using three tiers of
context matching, tried in order — fastest/most-certain first:

1. CONFIRMED ALIASES (confirmed_aliases.json) — exact string match against
   contexts a human has previously reviewed and confirmed via
   review_app.py. Free, instant, zero ambiguity. Grows over time as more
   documents get reviewed — the semantic layer below is needed less and
   less as this dictionary fills in.

2. REGEX (schema_registry.json's context_patterns) — hand-verified,
   exact-pattern matching for wording we've already confirmed by hand
   against real filings. Tries every context-matching family and accepts
   the one whose shape (field count) fits the row's actual value count —
   see _try_regex_families.

3. SEMANTIC (semantic_matcher.py) — only reached if NEITHER of the above
   found anything. Embedding-similarity match against each family's
   canonical_phrases. HIGH confidence auto-accepts (logged as
   match_method="semantic" for auditability); MEDIUM confidence returns
   status=ABSTAIN, reason="needs_review" with the candidate family and
   confidence attached, for human review; LOW confidence returns plain
   "unmapped".

THREE-VALUED STATUS (ACCEPT / ABSTAIN), not binary matched/unmapped — a
row can ABSTAIN for three distinct, inspectable reasons: "unmapped" (no
family identified at all), "shape_mismatch" (family identified via regex,
but value count doesn't fit), "needs_review" (semantic layer found a
plausible but uncertain match), or "validation_failed" (family + shape
matched, but a declared arithmetic rule failed).

NO NUMBER IS EVER GENERATED OR ALTERED HERE, at any tier. Values in
`fields` are always the exact strings row_parser.py extracted.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ingestion.row_parser import DataRow
from ingestion.schema_registry import SchemaRegistry, TableFamily, evaluate_rule, load_registry

CONFIRMED_ALIASES_PATH = Path(__file__).parent / "confirmed_aliases.json"


class ExtractionStatus(Enum):
    ACCEPT = "accept"
    ABSTAIN = "abstain"


@dataclass
class Provenance:
    schema_version: str
    section: str | None
    principle: int | None
    disclosure_question_id: str | None
    page: int | None
    context: str
    source_paragraph: str


@dataclass
class MappedRow:
    family_id: str
    status: ExtractionStatus
    reason: str  # "ok", "unmapped", "shape_mismatch", "validation_failed", "needs_review"
    fields: dict
    validation_results: dict
    provenance: Provenance
    row: DataRow
    match_method: str = "none"       # "confirmed_alias" | "regex" | "semantic" | "none"
    confidence: Optional[float] = None  # 1.0 for confirmed_alias/regex, cosine score for semantic


def _load_confirmed_aliases() -> dict:
    """Returns {exact_context_string: family_id}. Missing/empty file is
    normal — nothing has been confirmed yet."""
    if not CONFIRMED_ALIASES_PATH.exists():
        return {}
    try:
        entries = json.loads(CONFIRMED_ALIASES_PATH.read_text(encoding="utf-8"))
        return {e["context"]: e["family_id"] for e in entries}
    except (json.JSONDecodeError, OSError, KeyError):
        return {}


def _find_family(registry: SchemaRegistry, family_id: str) -> Optional[TableFamily]:
    return next((f for f in registry.families if f.family_id == family_id), None)


def _make_provenance(row: DataRow, family: Optional[TableFamily], schema_version: str) -> Provenance:
    return Provenance(
        schema_version=schema_version,
        section=family.section if family else None,
        principle=family.principle if family else None,
        disclosure_question_id=family.disclosure_question_id if family else None,
        page=row.page, context=row.context, source_paragraph=row.source_paragraph,
    )


def _bind_and_validate(row: DataRow, family: TableFamily, schema_version: str,
                        match_method: str, confidence: Optional[float]) -> MappedRow:
    provenance = _make_provenance(row, family, schema_version)

    if len(family.field_names) != len(row.values):
        return MappedRow(
            family_id=f"{family.family_id}_SHAPE_MISMATCH", status=ExtractionStatus.ABSTAIN,
            reason="shape_mismatch", fields={f"value_{i}": v for i, v in enumerate(row.values)},
            validation_results={}, provenance=provenance, row=row,
            match_method=match_method, confidence=confidence,
        )

    fields_bound = dict(zip(family.field_names, row.values))
    validation_results = {}
    any_failed = False
    for rule in family.validation_rules:
        result = evaluate_rule(rule, fields_bound)
        validation_results[f"{rule.rule_type}({rule.raw})"] = result
        if result is False:
            any_failed = True

    if any_failed:
        return MappedRow(
            family_id=family.family_id, status=ExtractionStatus.ABSTAIN, reason="validation_failed",
            fields=fields_bound, validation_results=validation_results, provenance=provenance,
            row=row, match_method=match_method, confidence=confidence,
        )

    return MappedRow(
        family_id=family.family_id, status=ExtractionStatus.ACCEPT, reason="ok",
        fields=fields_bound, validation_results=validation_results, provenance=provenance,
        row=row, match_method=match_method, confidence=confidence,
    )


def _try_regex_families(row: DataRow, registry: SchemaRegistry) -> Optional[MappedRow]:
    """Returns a MappedRow if any regex context_pattern matched (whether
    that results in ACCEPT or shape_mismatch) — or None if NO regex
    pattern matched at all, signaling the caller to try the semantic tier.
    """
    matching_families = [
        f for f in registry.families if any(p.search(row.context) for p in f.context_patterns)
    ]
    if not matching_families:
        return None

    for family in matching_families:
        if len(family.field_names) == len(row.values):
            return _bind_and_validate(row, family, registry.schema_version, "regex", 1.0)

    first = matching_families[0]
    return MappedRow(
        family_id=f"{first.family_id}_SHAPE_MISMATCH", status=ExtractionStatus.ABSTAIN,
        reason="shape_mismatch", fields={f"value_{i}": v for i, v in enumerate(row.values)},
        validation_results={}, provenance=_make_provenance(row, first, registry.schema_version),
        row=row, match_method="regex", confidence=1.0,
    )


def _try_semantic(row: DataRow, registry: SchemaRegistry) -> MappedRow:
    from ingestion.semantic_matcher import HIGH_CONFIDENCE, REVIEW_THRESHOLD, match_context

    candidate_id, confidence = match_context(row.context)

    if candidate_id and confidence >= HIGH_CONFIDENCE:
        family = _find_family(registry, candidate_id)
        if family:
            return _bind_and_validate(row, family, registry.schema_version, "semantic", confidence)

    if candidate_id and confidence >= REVIEW_THRESHOLD:
        family = _find_family(registry, candidate_id)
        if family and len(family.field_names) == len(row.values):
            fields = dict(zip(family.field_names, row.values))
        else:
            fields = {f"value_{i}": v for i, v in enumerate(row.values)}
        return MappedRow(
            family_id=candidate_id, status=ExtractionStatus.ABSTAIN, reason="needs_review",
            fields=fields, validation_results={},
            provenance=_make_provenance(row, family, registry.schema_version),
            row=row, match_method="semantic", confidence=confidence,
        )

    return MappedRow(
        family_id="unmapped", status=ExtractionStatus.ABSTAIN, reason="unmapped",
        fields={f"value_{i}": v for i, v in enumerate(row.values)}, validation_results={},
        provenance=_make_provenance(row, None, registry.schema_version),
        row=row, match_method="none", confidence=None,
    )


def map_row(row: DataRow, registry: SchemaRegistry, use_semantic: bool = True) -> MappedRow:
    # Tier 1: confirmed aliases — exact match, free, instant.
    aliases = _load_confirmed_aliases()
    if row.context in aliases:
        family = _find_family(registry, aliases[row.context])
        if family:
            return _bind_and_validate(row, family, registry.schema_version, "confirmed_alias", 1.0)

    # Tier 2: regex.
    regex_result = _try_regex_families(row, registry)
    if regex_result is not None:
        return regex_result

    # Tier 3: semantic fallback (only reached if regex matched NOTHING).
    if use_semantic:
        return _try_semantic(row, registry)

    return MappedRow(
        family_id="unmapped", status=ExtractionStatus.ABSTAIN, reason="unmapped",
        fields={f"value_{i}": v for i, v in enumerate(row.values)}, validation_results={},
        provenance=_make_provenance(row, None, registry.schema_version),
        row=row, match_method="none", confidence=None,
    )


def map_rows(rows: list[DataRow], registry: SchemaRegistry | None = None, use_semantic: bool = True) -> list[MappedRow]:
    registry = registry or load_registry()
    return [map_row(r, registry, use_semantic=use_semantic) for r in rows]


if __name__ == "__main__":
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    if len(sys.argv) != 2:
        print("Usage: python field_mapper.py path/to/extracted.json")
        sys.exit(1)

    from ingestion.row_parser import extract_data_rows

    data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    rows = extract_data_rows(data)
    registry = load_registry()
    mapped = map_rows(rows, registry)

    accepted = sum(1 for m in mapped if m.status == ExtractionStatus.ACCEPT)
    r_unmapped = sum(1 for m in mapped if m.reason == "unmapped")
    r_shape = sum(1 for m in mapped if m.reason == "shape_mismatch")
    r_valid = sum(1 for m in mapped if m.reason == "validation_failed")
    r_review = sum(1 for m in mapped if m.reason == "needs_review")
    m_regex = sum(1 for m in mapped if m.match_method == "regex" and m.status == ExtractionStatus.ACCEPT)
    m_semantic = sum(1 for m in mapped if m.match_method == "semantic" and m.status == ExtractionStatus.ACCEPT)
    m_alias = sum(1 for m in mapped if m.match_method == "confirmed_alias")

    print(f"{len(mapped)} total rows")
    print(f"  ACCEPT: {accepted}  (via regex: {m_regex}, via semantic: {m_semantic}, via confirmed_alias: {m_alias})")
    print(f"  ABSTAIN (unmapped): {r_unmapped}")
    print(f"  ABSTAIN (needs_review): {r_review}")
    print(f"  ABSTAIN (shape_mismatch): {r_shape}")
    print(f"  ABSTAIN (validation_failed): {r_valid}\n")

    for m in mapped:
        print(f"[page {m.row.page}] {m.status.value.upper()} family={m.family_id!r} reason={m.reason!r} method={m.match_method!r} confidence={m.confidence}")
        print(f"    label={m.row.label!r}")
        print(f"    context={m.provenance.context!r}")
        print(f"    fields={m.fields}")