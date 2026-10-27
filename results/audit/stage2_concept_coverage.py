"""Read-only inventory of Stage 2 concept-label coverage; does not create rater sheets."""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "03_bert_training"))

from build_training_dataset import (  # noqa: E402
    AI_SECTION_C_CONCEPT_TO_LABEL,
    NOTES_PRINCIPLE_CONCEPTS,
    PRINCIPLE_TO_LABEL,
    SECTION_C_CONCEPT_TO_LABEL,
    is_clean_narrative,
)
from db.models import Fact  # noqa: E402
from db.session import get_session  # noqa: E402


def main() -> None:
    raw = Counter()
    clean = Counter()
    explicit_axis = Counter()
    mapped_section_c = Counter()
    ai_section_c = Counter()
    notes = Counter()
    excluded = Counter()

    # Read existing facts only; do not call init_db() or modify the database.
    with get_session() as session:
        facts = (
            session.query(Fact.concept, Fact.value, Fact.dimensions)
            .filter(Fact.concept.like("%ExplanatoryTextBlock%"))
            .all()
        )

    for concept, value, dimensions in facts:
        if not value:
            continue
        raw[concept] += 1
        if not is_clean_narrative(value.strip()):
            continue
        clean[concept] += 1
        principle_dim = (dimensions or {}).get("PrincipleAxis")
        if principle_dim in PRINCIPLE_TO_LABEL:
            explicit_axis[concept] += 1
        elif concept in NOTES_PRINCIPLE_CONCEPTS:
            notes[concept] += 1
        elif concept in SECTION_C_CONCEPT_TO_LABEL:
            mapped_section_c[concept] += 1
            if concept in AI_SECTION_C_CONCEPT_TO_LABEL:
                ai_section_c[concept] += 1
        else:
            excluded[concept] += 1

    report = {
        "database_narrative_fact_rows": len(facts),
        "distinct_narrative_concepts": len(raw),
        "distinct_clean_concepts": len(clean),
        "explicit_principle_axis_concept_count": len(explicit_axis),
        "notes_principle_concept_count_present_in_db": len(notes),
        "section_c_mapped_concepts_present_in_db": len(mapped_section_c),
        "section_c_ai_mapped_concepts_present_in_db": len(ai_section_c),
        "section_c_clean_fact_rows_by_principle": {
            f"Principle{label + 1}Member": sum(
                count for concept, count in mapped_section_c.items()
                if SECTION_C_CONCEPT_TO_LABEL[concept] == label
            )
            for label in range(9)
        },
        "concepts_without_single_principle_mapping": sorted(excluded),
        "mapping_provenance": "AI weak-label extension; see results/audit/stage2_ai_mapping_provenance.md",
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
