"""
BRSR Data Row Parser — Phase 1

Problem this solves
--------------------
Many numeric BRSR disclosures (employee headcounts, wages, training coverage,
GHG/water/waste figures, etc.) are NOT real PDF tables — they are plain
positioned text that only *looks* tabular. No table-detection tool
(OpenDataLoader native/hybrid, pdfplumber, Camelot) can recover row structure
from them, because there is no graphical table structure to detect.

This module recovers that structure directly from the text: it walks
OpenDataLoader's extracted JSON, finds paragraphs/list-items containing BRSR
data, and splits them into individual rows by alternating "label" and "value"
token runs. It also tracks `context` — the nearest preceding text that looks
like a real SEBI disclosure question — needed because multiple BRSR table
families share identical numeric shapes and can only be told apart by the
question text that precedes them (see field_mapper.py).

CRITICAL structural note (found by dumping real Glenmark JSON, not assumed):
OpenDataLoader uses THREE different keys for a node's children depending on
type, and a parser that only checks one silently misses real content:
  - "kids"        — general parent-child (headings, most paragraphs)
  - "list items"  — list-type nodes' real children (note: NOT "kids")
  - "rows" -> "cells" -> "kids" — table-type nodes
Real BRSR tables mix these unpredictably even within the same document.

Verified against two independently-generated BRSR filings (Glenmark
Pharmaceuticals and Aequs Limited — different sectors, different PDF
generation tooling) with hand-checked ground truth. See tests/test_row_parser.py.

Explicit scope and limitations (read before use)
--------------------------------------------------
- This module recovers ROW STRUCTURE (label + ordered list of values) and
  CONTEXT (nearest real disclosure question). It does NOT map values to
  named fields — that's field_mapper.py, separate and schema-driven.
- `check_two_part_breakdown` is ADVISORY ONLY. It holds for some BRSR table
  families (minimum wages: Total = Equal-to-min + More-than-min) and does NOT
  hold for others (wellbeing coverage, where the first value is a headcount
  base, not a sum). MISMATCH means "doesn't fit this shape," not "wrong data."
- Candidate detection requires a minimum value-token count per paragraph and
  will still occasionally pick up narrative sentences with several numbers.
- Footnote markers (*, **, ^) trailing a numeric token are stripped and
  recorded separately rather than breaking the row split.
- MIN_VALUE_TOKENS_FOR_CANDIDATE is deliberately low (2) so small legitimate
  tables (e.g. "Gross wages paid to females...", exactly 2 values) aren't
  silently dropped before ever becoming a candidate row — verified real bug
  on Glenmark data. This makes question/heading text with incidental
  digit-like tokens (e.g. "22. Turnover rate... past 3 years:") more likely
  to be misread as a data row — fixed via _is_disclosure_question_intro,
  which checks for a trailing ":" (verified: every real disclosure question
  observed so far ends with ":"; real numbered data rows never do — they
  end with a number) and takes priority over row-candidate detection.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


# Allows an optional leading ₹ (rupee symbol) — real Glenmark source text
# has currency values as a SEPARATE preceding token ("₹ 4,96,55,753"), and
# without this the ₹ token was neither a value nor stripped, corrupting
# row segmentation for the median remuneration table (wrong values ended
# up bleeding across adjacent rows).
VALUE_RE = re.compile(r"^₹?-?[\d,]+\.?\d*%?$")
# Includes Yes/No/Y/N alongside true "missing data" markers. Real BRSR
# tables (e.g. retirement benefits' "Deducted and deposited with the
# authority (Y/N/N.A.)" column) have categorical Yes/Y/No/N answers sitting
# in the same position as numeric values — verified real bug: without
# these, "Yes"/"Y" was treated as a label token, splitting a single real
# row (PF/ESI, both companies) into fragments. to_number() already returns
# None for anything in this set, which is the correct behavior for these
# too (they're not numeric, but they ARE legitimate value-slot tokens).
NA_TOKENS = {"N/A", "NA", "NIL", "-", "Yes", "No", "Y", "N"}
FOOTNOTE_RE = re.compile(r"^(.*?)([*^]+)$")

MIN_VALUE_TOKENS_FOR_CANDIDATE = 2
MIN_VALUES_PER_ROW = 2

ROW_CANDIDATE_TYPES = ("list item", "paragraph")

NUMBERED_QUESTION_RE = re.compile(r"^(\d+\.?\s*[a-z]?\.?\s|[a-z]\.\s)")

MIN_CONTEXT_LENGTH = 25


def _is_value_token(tok: str) -> bool:
    return bool(VALUE_RE.match(tok)) or tok in NA_TOKENS


def _strip_footnote(tok: str) -> tuple[str, Optional[str]]:
    m = FOOTNOTE_RE.match(tok)
    if m and _is_value_token(m.group(1)):
        return m.group(1), m.group(2)
    return tok, None


def to_number(tok: str) -> Optional[float]:
    if tok in NA_TOKENS:
        return None
    return float(tok.replace(",", "").replace("%", ""))


@dataclass
class DataRow:
    page: Optional[int]
    label: str
    values: list[str]
    footnotes: list[str] = field(default_factory=list)
    source_paragraph: str = ""
    context: str = ""


class ReconciliationStatus(Enum):
    FITS = "fits"
    MISMATCH = "mismatch"
    SKIPPED = "skipped"


@dataclass
class ReconciliationResult:
    status: ReconciliationStatus
    message: str


def check_two_part_breakdown(values: list[str]) -> ReconciliationResult:
    if len(values) < 4:
        return ReconciliationResult(ReconciliationStatus.SKIPPED, "too few values for this check")
    total, part_a, part_b = to_number(values[0]), to_number(values[1]), to_number(values[3])
    if total is None or part_a is None or part_b is None:
        return ReconciliationResult(ReconciliationStatus.SKIPPED, "N/A present in checked positions")
    if abs((part_a + part_b) - total) < 0.5:
        return ReconciliationResult(ReconciliationStatus.FITS, f"{part_a} + {part_b} = {total}")
    return ReconciliationResult(
        ReconciliationStatus.MISMATCH,
        f"{part_a} + {part_b} != {total} — doesn't fit this shape, not necessarily wrong",
    )


def split_into_rows(content: str, page: Optional[int] = None) -> list[DataRow]:
    tokens = content.split()

    # Merge a standalone "₹" token into the NEXT token, since real source
    # text renders currency as two separate tokens ("₹ 4,96,55,753") — left
    # unmerged, "₹" is neither a value nor a label word, and silently
    # dropping it (rather than merging) shifts token positions enough to
    # corrupt row segmentation (verified real bug: Glenmark's median
    # remuneration table, values bled across adjacent Male/Female rows).
    merged_tokens = []
    skip_next_merge = False
    for i, tok in enumerate(tokens):
        if skip_next_merge:
            skip_next_merge = False
            continue
        if tok == "₹" and i + 1 < len(tokens):
            merged_tokens.append("₹" + tokens[i + 1])
            skip_next_merge = True
        else:
            merged_tokens.append(tok)
    tokens = merged_tokens

    rows: list[DataRow] = []
    label_buf: list[str] = []
    value_buf: list[str] = []
    footnote_buf: list[str] = []

    def flush():
        if value_buf:
            rows.append(
                DataRow(
                    page=page,
                    label=" ".join(label_buf).strip(),
                    values=list(value_buf),
                    footnotes=list(footnote_buf),
                    source_paragraph=content,
                )
            )

    for tok in tokens:
        clean, marker = _strip_footnote(tok)
        if _is_value_token(clean):
            value_buf.append(clean)
            if marker:
                footnote_buf.append(f"{clean}{marker}")
        else:
            if value_buf:
                flush()
                label_buf, value_buf, footnote_buf = [], [], []
            label_buf.append(tok)
    flush()

    return [r for r in rows if len(r.values) >= MIN_VALUES_PER_ROW]


def _count_value_tokens(content: str) -> int:
    count = 0
    for tok in content.split():
        clean, _ = _strip_footnote(tok)
        if _is_value_token(clean):
            count += 1
    return count


def _looks_like_real_context(content: str, node_type: str) -> bool:
    if len(content) < MIN_CONTEXT_LENGTH:
        return False
    if node_type == "heading":
        return True
    return bool(NUMBERED_QUESTION_RE.match(content))


def _is_disclosure_question_intro(content: str, node_type: str) -> bool:
    """True if this text is almost certainly introducing a table/question
    rather than being data itself — even if it happens to contain enough
    digit-like tokens to otherwise pass the row-candidate threshold.

    Fixes a real regression found on Glenmark data: lowering
    MIN_VALUE_TOKENS_FOR_CANDIDATE from 4 to 2 caused "22. Turnover rate
    for permanent employees and workers (Disclose trends for the past 3
    years):" to be misread as a 2-value data row (from "22." and "3" both
    matching VALUE_RE), instead of being recognized as a question — which
    broke context propagation for the real turnover data that followed it.

    Every real disclosure question context string collected across this
    project so far ends with ":" (verified empirically, not assumed); real
    numbered data rows (e.g. "1. Permanent (D) 12,312 11,371 92% 941 8%")
    never do — they end with a number. This check takes priority over
    row-candidate detection specifically for that reason.
    """
    return content.rstrip().endswith(":") and _looks_like_real_context(content, node_type)


def _children_of(node: dict):
    for child in node.get("kids", []):
        yield child
    for item in node.get("list items", []):
        yield item
    for row in node.get("rows", []):
        for cell in row.get("cells", []):
            for kid in cell.get("kids", []):
                yield kid


def extract_data_rows(structured_json: dict) -> list[DataRow]:
    all_rows: list[DataRow] = []

    def walk(node, inherited_context: str) -> str:
        if isinstance(node, dict):
            content = node.get("content")
            node_type = node.get("type")
            current_context = inherited_context

            if content:
                if _is_disclosure_question_intro(content, node_type):
                    current_context = content
                elif node_type in ROW_CANDIDATE_TYPES and _count_value_tokens(content) >= MIN_VALUE_TOKENS_FOR_CANDIDATE:
                    rows = split_into_rows(content, page=node.get("page number"))
                    for r in rows:
                        r.context = inherited_context
                    all_rows.extend(rows)
                elif _looks_like_real_context(content, node_type):
                    current_context = content

            for child in _children_of(node):
                current_context = walk(child, current_context)
            return current_context

        elif isinstance(node, list):
            current_context = inherited_context
            for item in node:
                current_context = walk(item, current_context)
            return current_context

        return inherited_context

    walk(structured_json, inherited_context="")
    return all_rows


if __name__ == "__main__":
    import io
    import json
    import sys

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    if len(sys.argv) != 2:
        print("Usage: python row_parser.py path/to/extracted.json")
        sys.exit(1)

    data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    rows = extract_data_rows(data)
    print(f"Found {len(rows)} data row(s)\n")
    for r in rows:
        check = check_two_part_breakdown(r.values)
        footnote_note = f"  [footnotes: {r.footnotes}]" if r.footnotes else ""
        print(f"[page {r.page}] context={r.context!r}")
        print(f"    {r.label!r} -> {r.values}{footnote_note}")
        print(f"    {check.status.value}: {check.message}")