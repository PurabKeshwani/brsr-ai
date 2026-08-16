"""
Test hypothesis: pdfplumber's line-based strategy correctly found table headers
(meaning real vertical column lines exist), but data rows are missing — meaning
there are likely no horizontal lines below the header to mark row boundaries.

Fix to test: keep "lines" for vertical (column) detection since that worked,
switch to "text" for horizontal (row) detection so rows get found by text
position instead of requiring a ruling line.

Usage:
    python scripts/pdfplumber_mixed_strategy.py data/raw_pdfs/glenmark.pdf
"""
import sys
from pathlib import Path

import pdfplumber

TARGET_PAGES = [4, 20]

MIXED_STRATEGY = {
    "vertical_strategy": "lines",   # columns: use real ruling lines (this worked)
    "horizontal_strategy": "text",  # rows: infer from text position instead
    "snap_tolerance": 5,
    "intersection_tolerance": 5,
}


def dump_page(pdf, page_num: int) -> None:
    page = pdf.pages[page_num - 1]
    print(f"\n{'=' * 60}\nPage {page_num}\n{'=' * 60}")

    tables = page.extract_tables(table_settings=MIXED_STRATEGY)
    print(f"{len(tables)} table(s) found\n")

    for i, table in enumerate(tables):
        n_rows = len(table)
        n_cols = max((len(row) for row in table), default=0)
        print(f"--- Table {i} ({n_rows} rows x {n_cols} cols) ---")
        for row in table:
            clean_row = [(cell or "").replace("\n", " ") for cell in row]
            print(" | ".join(clean_row))
        print()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python pdfplumber_mixed_strategy.py path/to/glenmark.pdf")
        sys.exit(1)

    pdf_path = Path(sys.argv[1])
    with pdfplumber.open(pdf_path) as pdf:
        for page_num in TARGET_PAGES:
            dump_page(pdf, page_num)