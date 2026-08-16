"""
BRSR Schema Registry — Phase 2 refactor

Replaces field_mapper.py's hardcoded Python SCHEMAS list with data-driven
schemas loaded from schema_registry.json. This makes the registry itself
(context patterns, field names, validation rules, SEBI provenance metadata)
inspectable, editable, and versionable independently of extraction code —
per the architecture review: "build the schema registry as actual data
(YAML/JSON per family), not comments in code — cheap now, expensive later."

Validation rules are STRUCTURED DATA (not free-form expressions/eval()) —
each rule has a fixed "type" with a small, safe set of operations. This is
deliberate: no arbitrary code execution risk, and every rule type is
individually auditable.

Supported rule types:
- "sum_equals": sum(operands) == target, within tolerance
- "le": field <= bound_field (a subset/coverage count can't exceed its base)
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

REGISTRY_PATH = Path(__file__).parent / "schema_registry.json"


@dataclass
class ValidationRule:
    rule_type: str
    raw: dict  # original rule dict, kept for reference/debugging


@dataclass
class TableFamily:
    family_id: str
    section: Optional[str]
    principle: Optional[int]
    disclosure_question_id: Optional[str]
    context_patterns: list[re.Pattern]
    field_names: list[str]
    units: dict
    validation_rules: list[ValidationRule]
    notes: str = ""


@dataclass
class SchemaRegistry:
    schema_version: str
    families: list[TableFamily]


def load_registry(path: Path = REGISTRY_PATH) -> SchemaRegistry:
    data = json.loads(path.read_text(encoding="utf-8"))
    families = []
    for f in data["families"]:
        families.append(
            TableFamily(
                family_id=f["family_id"],
                section=f.get("section"),
                principle=f.get("principle"),
                disclosure_question_id=f.get("disclosure_question_id"),
                context_patterns=[re.compile(p, re.I) for p in f["context_patterns"]],
                field_names=f["field_names"],
                units=f.get("units", {}),
                validation_rules=[ValidationRule(r["type"], r) for r in f.get("validation_rules", [])],
                notes=f.get("notes", ""),
            )
        )
    return SchemaRegistry(schema_version=data["schema_version"], families=families)


def _to_number(tok: str) -> Optional[float]:
    if tok in {"N/A", "NA", "NIL", "-"}:
        return None
    try:
        return float(tok.replace(",", "").replace("%", ""))
    except ValueError:
        return None


def evaluate_rule(rule: ValidationRule, fields: dict) -> Optional[bool]:
    """Evaluates one validation rule against bound field values.
    Returns True (passes), False (fails), or None (skipped — e.g. an
    operand is N/A, so the rule doesn't apply to this row, which is
    different from failing it).
    """
    if rule.rule_type == "sum_equals":
        operand_vals = [_to_number(fields.get(op, "")) for op in rule.raw["operands"]]
        target_val = _to_number(fields.get(rule.raw["target"], ""))
        if target_val is None or any(v is None for v in operand_vals):
            return None
        tolerance = rule.raw.get("tolerance", 0.5)
        return abs(sum(operand_vals) - target_val) < tolerance

    if rule.rule_type == "le":
        field_val = _to_number(fields.get(rule.raw["field"], ""))
        bound_val = _to_number(fields.get(rule.raw["bound_field"], ""))
        if field_val is None or bound_val is None:
            return None
        return field_val <= bound_val + 0.5  # small tolerance for rounding

    return None  # unknown rule type — treat as not-evaluable, not a failure