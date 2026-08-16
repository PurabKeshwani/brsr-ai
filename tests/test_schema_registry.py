import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ingestion.schema_registry import ValidationRule, evaluate_rule, load_registry


def test_registry_loads_every_family_defined_in_json_with_no_duplicates():
    """Doesn't hardcode family names/count — compares against the JSON file
    itself, so this test never needs editing when a new family is added.
    Still catches real bugs: a malformed entry silently dropped by
    _load_discovered_schemas-style try/except, a duplicate family_id, or a
    regex that fails to compile.
    """
    import json
    from ingestion.schema_registry import REGISTRY_PATH

    raw = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    expected_ids = [f["family_id"] for f in raw["families"]]

    registry = load_registry()
    loaded_ids = [f.family_id for f in registry.families]

    assert len(loaded_ids) == len(raw["families"]), "some family in the JSON failed to load"
    assert set(loaded_ids) == set(expected_ids)
    assert len(loaded_ids) == len(set(loaded_ids)), "duplicate family_id found in registry"


def test_sum_equals_passes_on_real_verified_data():
    rule = ValidationRule("sum_equals", {"operands": ["male_count", "female_count"], "target": "total", "tolerance": 0.5})
    fields = {"total": "12,708", "male_count": "11,697", "female_count": "1,011"}
    assert evaluate_rule(rule, fields) is True


def test_sum_equals_skips_on_na_not_fails():
    rule = ValidationRule("sum_equals", {"operands": ["male_count", "female_count"], "target": "total", "tolerance": 0.5})
    fields = {"total": "-", "male_count": "-", "female_count": "-"}
    assert evaluate_rule(rule, fields) is None


def test_le_rule_passes_when_subset_within_bound():
    rule = ValidationRule("le", {"field": "union_members_current_fy", "bound_field": "total_current_fy"})
    fields = {"union_members_current_fy": "242", "total_current_fy": "11,641"}
    assert evaluate_rule(rule, fields) is True