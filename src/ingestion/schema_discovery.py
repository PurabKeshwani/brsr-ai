"""
Schema Discovery Tool — Phase 2, LLM-assisted (Gemini)

Problem this solves
--------------------
field_mapper.py's locked SCHEMAS list is deterministic and hand-verified —
but writing every one of SEBI's ~35-40 BRSR table-family schemas by hand (we
hit 4 real bugs across just the first 7, across only two companies) does not
scale to full coverage or to wording variations across 1,000+ filers.

This tool proposes NEW schemas for rows field_mapper.py doesn't recognize
yet, using Gemini to suggest FIELD NAMES for a row's positional values.

Safety model — read this before trusting any output
-------------------------------------------------------
1. Gemini NEVER sees a task that could change a number. It's given the
   context question, the row's label, and the ALREADY-EXTRACTED values as
   read-only reference — its only output is a list of field-name labels,
   same length as the input values. The numeric values used anywhere
   downstream always come directly from row_parser.py, never from Gemini.
2. Every response is validated: len(field_names) MUST exactly equal
   len(values). Mismatches are rejected, not guessed around.
3. Gemini is called ONCE PER UNIQUE CONTEXT STRING, ever — cached in
   schema_llm_cache.json. Since SEBI's format is fixed, a new company
   reusing standard wording costs nothing.
4. NOTHING this tool produces is used in production automatically. Output
   goes to schema_candidates.json for HUMAN REVIEW ONLY. A schema only
   becomes real (used by field_mapper.py) after a person manually copies a
   reviewed entry into discovered_schemas.json.
5. Generated context_pattern values are an ESCAPED, near-exact match of the
   real observed context string — not a loose guess — to minimize the risk
   of a new schema accidentally cross-matching rows it shouldn't (the exact
   bug class we hit by hand 4 times already; see field_mapper.py docstring).

Setup
-----
    pip install google-genai python-dotenv
    Create a .env file in the project root with:
        GEMINI_API_KEY=your_key_here
    (Get a free key at https://aistudio.google.com/apikey)

Usage
-----
    python src/ingestion/schema_discovery.py data/extracted/glenmark.json
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ingestion.field_mapper import SCHEMAS, _load_discovered_schemas
from ingestion.row_parser import DataRow, extract_data_rows

CACHE_PATH = Path(__file__).parent / "schema_llm_cache.json"
CANDIDATES_PATH = Path(__file__).parent / "schema_candidates.json"

# Skip very short/noisy rows (letterhead phone numbers, page footers, etc.)
# — not worth an LLM call, and unlikely to be a real disclosure table.
MIN_VALUES_TO_CONSIDER = 3

# Model name as documented by Google as of Aug 2026. If this errors with a
# "model not found" style message, check https://ai.google.dev/gemini-api/docs/models
# for the current free-tier model your API key has access to and change this.
GEMINI_MODEL = "gemini-2.5-flash"

# Safety cap on LLM calls per run — avoids accidentally burning free-tier
# quota on one run if a document has many unmapped contexts.
MAX_CALLS_PER_RUN = 20


def _sanitize_field_name(name: str) -> str:
    """Light cleanup so LLM-suggested names are usable Python-ish identifiers
    even if the model doesn't follow the snake_case instruction perfectly."""
    name = re.sub(r"[^a-zA-Z0-9_]", "_", name.strip().lower())
    name = re.sub(r"_+", "_", name).strip("_")
    return name or "field"


def _load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def _save_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _group_unmapped_by_context(rows: list[DataRow], already_mapped_names: set[str]) -> dict[str, DataRow]:
    """Returns {context_string: representative_row} for unique unmapped
    contexts — one representative row per unique context, since asking
    Gemini about every row with the same context would be wasteful and
    redundant (they'd all get the same answer)."""
    from ingestion.field_mapper import map_row

    schemas = SCHEMAS + _load_discovered_schemas()
    groups: dict[str, DataRow] = {}

    for row in rows:
        if len(row.values) < MIN_VALUES_TO_CONSIDER:
            continue
        mapped = map_row(row, schemas=schemas)
        if mapped.schema_matched:
            continue  # already handled by an existing schema
        if mapped.schema_name.endswith("_SHAPE_MISMATCH"):
            continue  # different problem — an existing schema's shape is wrong, not a missing one
        if row.context not in groups:
            groups[row.context] = row

    return groups


def _build_prompt(context: str, row: DataRow) -> str:
    return f"""You are helping build a deterministic data-extraction pipeline for India's SEBI-mandated BRSR (Business Responsibility and Sustainability Report) regulatory filings.

A row of data was extracted from a BRSR PDF. The row's ORDERED VALUES were extracted exactly as printed in the source document — do not alter, reinterpret, or output the values themselves.

Your ONLY job: propose a short, descriptive snake_case field name for EACH value, in the same order, based on what it most likely represents given the disclosure question (context) it appeared under. Also propose a short snake_case name for this table family overall.

Disclosure question (context) this row appeared under:
"{context}"

Row label (may be empty, or a category like "Male"/"Female"/"Permanent"):
"{row.label}"

Ordered values (there are exactly {len(row.values)}):
{row.values}

Respond with ONLY a JSON object in this exact shape, nothing else:
{{
  "table_family_name": "short_snake_case_name",
  "field_names": ["field_for_value_0", "field_for_value_1", ...]
}}

The "field_names" list MUST have EXACTLY {len(row.values)} entries, one per value, in the same order. Do not include the values themselves anywhere in your response — only field name labels."""


def discover_schemas(extracted_json_path: str) -> None:
    from dotenv import load_dotenv
    load_dotenv()

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY not found. Create a .env file with GEMINI_API_KEY=your_key_here")
        sys.exit(1)

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)

    data = json.loads(Path(extracted_json_path).read_text(encoding="utf-8"))
    rows = extract_data_rows(data)

    cache = _load_json(CACHE_PATH, {})
    candidates = _load_json(CANDIDATES_PATH, [])
    already_candidate_contexts = {c["source_context"] for c in candidates}

    groups = _group_unmapped_by_context(rows, already_candidate_contexts)
    print(f"{len(groups)} unique unmapped context(s) found in this document.\n")

    calls_made = 0
    new_candidates = []

    for context, row in groups.items():
        if context in cache:
            status = cache[context].get("status")
            print(f"SKIP (cached, {status}): {context[:70]!r}")
            continue
        if context in already_candidate_contexts:
            print(f"SKIP (already a candidate): {context[:70]!r}")
            continue
        if calls_made >= MAX_CALLS_PER_RUN:
            print(f"SKIP (hit MAX_CALLS_PER_RUN={MAX_CALLS_PER_RUN}): {context[:70]!r}")
            continue

        print(f"Asking Gemini about: {context[:70]!r} ({len(row.values)} values)...")
        prompt = _build_prompt(context, row)

        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json"),
            )
            calls_made += 1
            result = json.loads(response.text)
            field_names = [_sanitize_field_name(f) for f in result.get("field_names", [])]
            table_family_name = _sanitize_field_name(result.get("table_family_name", "unknown_table"))
        except Exception as e:
            print(f"  FAILED: {e}")
            cache[context] = {"status": "error", "error": str(e)}
            continue

        if len(field_names) != len(row.values):
            print(f"  REJECTED: got {len(field_names)} field names for {len(row.values)} values — mismatch")
            cache[context] = {
                "status": "rejected_shape_mismatch",
                "expected": len(row.values),
                "got": len(field_names),
            }
            continue

        candidate = {
            "name": table_family_name,
            "context_pattern": re.escape(context[:80]),  # near-exact match, safe by default
            "field_names": field_names,
            "source_context": context,
            "sample_label": row.label,
            "sample_values": row.values,
            "sample_page": row.page,
        }
        new_candidates.append(candidate)
        cache[context] = {"status": "accepted", "table_family_name": table_family_name, "field_names": field_names}
        print(f"  ACCEPTED: {table_family_name} -> {dict(zip(field_names, row.values))}")

    _save_json(CACHE_PATH, cache)
    if new_candidates:
        candidates.extend(new_candidates)
        _save_json(CANDIDATES_PATH, candidates)

    print(f"\n{len(new_candidates)} new candidate(s) written to {CANDIDATES_PATH}")
    print(
        "\nNEXT STEP (manual, by design): open schema_candidates.json, review each "
        "candidate against the actual source PDF, then copy the ones you approve "
        "into discovered_schemas.json (same format, minus the sample_* fields). "
        "Nothing here is used by field_mapper.py until you do that."
    )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python schema_discovery.py path/to/extracted.json")
        sys.exit(1)
    discover_schemas(sys.argv[1])