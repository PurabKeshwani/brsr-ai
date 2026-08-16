"""
Prints the actual cell content of tables detected by the hybrid backend, so you can
visually check it against the source PDF — table shape (rows x cols) matching doesn't
guarantee the values landed in the right cells.

Usage:
    python scripts/dump_table_content.py data/extracted/diagnostic/hybrid_docling/glenmark.json
"""
import json
import sys
from pathlib import Path


def cell_text(cell: dict) -> str:
    """Flatten a table cell's nested paragraph content into one string."""
    parts = [k.get("content", "") for k in cell.get("kids", []) if k.get("content")]
    return " ".join(parts).strip()


def dump_table(table: dict, index: int) -> None:
    page = table.get("page number")
    n_rows = table.get("number of rows")
    n_cols = table.get("number of columns")
    print(f"\n--- Table {index} (page {page}, {n_rows} rows x {n_cols} cols) ---")
    for row in table.get("rows", []):
        cells = row.get("cells", [])
        texts = [cell_text(c) for c in cells]
        print(" | ".join(texts))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python dump_table_content.py path/to/extracted.json")
        sys.exit(1)

    json_path = Path(sys.argv[1])
    data = json.loads(json_path.read_text(encoding="utf-8"))
    tables = [el for el in data.get("kids", []) if el.get("type") == "table"]

    print(f"Found {len(tables)} table(s) in {json_path.name}")
    for i, table in enumerate(tables):
        dump_table(table, i)