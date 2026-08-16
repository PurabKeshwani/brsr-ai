"""
Diagnostic: can pdfplumber's text-based (borderless) table strategy detect the
numeric ESG tables that OpenDataLoader's native cluster mode missed?

This is a much lighter alternative to standing up the OpenDataLoader hybrid AI
backend (which pulls in ~5GB of ML dependencies) — pdfplumber is pure Python plus
a couple of small deps, installs in seconds, and has a strategy designed exactly
for this case: tables with no visible ruling lines, where columns are implied by
consistent horizontal gaps between text runs.

Usage:
    pip install pdfplumber
    python scripts/pdfplumber_table_check.py data/raw_pdfs/glenmark.pdf
"""
import sys
from pathlib import Path

import pdfplumber

# Known-problem pages from the native OpenDataLoader run (1-indexed, human page numbers):
# page 4 = employee headcount table, page 20 = workforce well-being table.
TARGET_PAGES = [4, 20]

# pdfplumber's default table_settings assume ruling lines. This strategy instead
# infers rows/columns purely from the gaps between text positions — the right
# approach for whitespace-aligned tables with no borders.
TEXT_STRATEGY = {
    "vertical_strategy": "text",
    "horizontal_strategy": "text",
    "snap_tolerance": 5,
    "intersection_tolerance": 5,
}


def check_page(pdf, page_num: int) -> None:
    page = pdf.pages[page_num - 1]  # pdfplumber is 0-indexed
    print(f"\n{'=' * 60}\nPage {page_num}\n{'=' * 60}")

    default_tables = page.extract_tables()
    print(f"Default (line-based) strategy: {len(default_tables)} table(s) found")

    text_tables = page.extract_tables(table_settings=TEXT_STRATEGY)
    print(f"Text-based (borderless) strategy: {len(text_tables)} table(s) found")

    for i, table in enumerate(text_tables):
        n_rows = len(table)
        n_cols = max((len(row) for row in table), default=0)
        print(f"  Table {i}: {n_rows} rows x {n_cols} cols")
        print(f"    Header row: {table[0]}")
        if n_rows > 1:
            print(f"    Row 1:      {table[1]}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python pdfplumber_table_check.py path/to/glenmark.pdf")
        sys.exit(1)

    pdf_path = Path(sys.argv[1])
    with pdfplumber.open(pdf_path) as pdf:
        print(f"Opened {pdf_path.name}: {len(pdf.pages)} pages")
        for page_num in TARGET_PAGES:
            check_page(pdf, page_num)

    print(
        "\nIf the text-based strategy shows real row/col counts (not 0) matching "
        "what you see in the actual PDF on these pages, pdfplumber's text strategy "
        "is a viable path for the numeric ESG tables — next step would be deciding "
        "whether to run it as a full secondary pass, or only on OpenDataLoader "
        "paragraphs flagged as suspiciously number-heavy (see compare_native_vs_"
        "hybrid.py's digit-density check for that heuristic)."
    )