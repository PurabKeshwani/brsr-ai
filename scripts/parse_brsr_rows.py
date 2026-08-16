"""
BRSR rows aren't real PDF tables in many places — they're plain positioned text
that only *looks* like a table, and OpenDataLoader native mode often merges
MULTIPLE logical rows into one paragraph string. This splits a merged string
into its real rows by alternating label-runs and value-runs, then applies a
structural "Total = PartA + PartB" check ONLY as an advisory signal — this
pattern holds for some BRSR table families (e.g. min-wage: Equal + More-than =
Total) but NOT others (e.g. wellbeing coverage: Total is a headcount base, not
a sum) — so a "MISMATCH" here means "doesn't fit this specific shape," not
necessarily "wrong data." Read it as a hint to inspect, not a verdict.

Usage:
    python scripts/parse_brsr_rows.py data/extracted/glenmark.json
"""
import json
import re
import sys
from pathlib import Path

VALUE_RE = re.compile(r"^-?[\d,]+\.?\d*%?$")
NA_TOKENS = {"N/A", "NA", "NIL", "-"}


def is_value_token(tok: str) -> bool:
    return bool(VALUE_RE.match(tok)) or tok in NA_TOKENS


def split_into_rows(content: str):
    """Alternates label-runs and value-runs: every time a value-run ends and a
    new label-run starts, that's a new row. Fixes the old bug where one merged
    paragraph (containing many real table rows) was treated as a single row."""
    tokens = content.split()
    rows = []
    label_buf, value_buf = [], []
    for tok in tokens:
        if is_value_token(tok):
            value_buf.append(tok)
        else:
            if value_buf:
                rows.append((" ".join(label_buf).strip(), value_buf))
                label_buf, value_buf = [], []
            label_buf.append(tok)
    if value_buf:
        rows.append((" ".join(label_buf).strip(), value_buf))
    return rows


def to_number(tok: str):
    if tok in NA_TOKENS:
        return None
    return float(tok.replace(",", "").replace("%", ""))


def check_two_way_breakdown(values: list[str]) -> str:
    """Advisory only: checks values[0] == values[1] + values[3], which holds
    for 'Total = PartA + PartB' style tables (min wages, differently-abled,
    etc.) but NOT for tables where the first column is a per-row base rather
    than a sum (e.g. wellbeing coverage %). Treat MISMATCH as "doesn't fit
    this shape," not automatically "wrong.\""""
    if len(values) < 4:
        return "skip (too few values for this check)"
    total, part_a, part_b = to_number(values[0]), to_number(values[1]), to_number(values[3])
    if total is None or part_a is None or part_b is None:
        return "skip (N/A present)"
    if abs((part_a + part_b) - total) < 0.5:
        return f"fits Total=PartA+PartB  ({part_a} + {part_b} = {total})"
    return f"doesn't fit that shape  ({part_a} + {part_b} != {total}) — check table type"


def collect_candidate_paragraphs(node, results):
    if isinstance(node, dict):
        content = node.get("content")
        if content and node.get("type") in ("list item", "paragraph"):
            row_count = sum(1 for tok in content.split() if is_value_token(tok))
            if row_count >= 2:
                results.append({"page": node.get("page number"), "content": content})
        for child in node.get("kids", []):
            collect_candidate_paragraphs(child, results)
    elif isinstance(node, list):
        for item in node:
            collect_candidate_paragraphs(item, results)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python parse_brsr_rows.py path/to/extracted.json")
        sys.exit(1)

    data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    paragraphs = []
    collect_candidate_paragraphs(data, paragraphs)

    print(f"Found {len(paragraphs)} candidate paragraph(s) containing numeric data\n")
    for p in paragraphs:
        rows = split_into_rows(p["content"])
        if len(rows) <= 1:
            continue  # nothing interesting to show for single-row paragraphs here
        print(f"[page {p['page']}] paragraph split into {len(rows)} row(s):")
        for label, values in rows:
            check = check_two_way_breakdown(values)
            print(f"    {label!r} -> {values}")
            print(f"        {check}")
        print()