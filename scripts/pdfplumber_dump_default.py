"""
Dumps full content of tables found by pdfplumber's DEFAULT (line-based) strategy,
since the initial check showed promising table counts (5 on page 4, 4 on page 20) —
worth verifying whether the content inside is actually correct before committing
to this path.

Usage:
    python scripts/pdfplumber_dump_default.py data/raw_pdfs/glenmark.pdf
"""
import sys
from pathlib import Path

import pdfplumber

TARGET_PAGES = [4, 20]


def dump_page(pdf, page_num: int) -> None:
    page = pdf.pages[page_num - 1]
    print(f"\n{'=' * 60}\nPage {page_num}\n{'=' * 60}")

    tables = page.extract_tables()  # default line-based strategy
    print(f"{len(tables)} table(s) found\n")

    for i, table in enumerate(tables):
        n_rows = len(table)
        n_cols = max((len(row) for row in table), default=0)
        print(f"--- Table {i} ({n_rows} rows x {n_cols} cols) ---")
        for row in table:
            # Replace None cells (common in pdfplumber output) with empty string
            clean_row = [cell if cell is not None else "" for cell in row]
            print(" | ".join(clean_row))
        print()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python pdfplumber_dump_default.py path/to/glenmark.pdf")
        sys.exit(1)

    pdf_path = Path(sys.argv[1])
    with pdfplumber.open(pdf_path) as pdf:
        for page_num in TARGET_PAGES:
            dump_page(pdf, page_num)