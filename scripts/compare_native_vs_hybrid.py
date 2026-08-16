"""
Diagnostic: compare OpenDataLoader's native (cluster) table detection against the
hybrid AI backend on the specific pages where native mode failed on the Glenmark
BRSR filing — page 4 (employee headcount table) and page 20 (workforce well-being
table), both borderless/whitespace-aligned numeric tables.

Prerequisites (run in a separate terminal, leave running):
    pip install "opendataloader-pdf[hybrid]"
    opendataloader-pdf-hybrid --port 5002

Usage:
    python scripts/compare_native_vs_hybrid.py path/to/glenmark.pdf
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ingestion.extractor import extract, ExtractionError

TEST_PAGES = "4,20"  # known-problem pages: borderless numeric tables


def summarize(label: str, out_dir: Path, pdf_path: Path) -> None:
    print(f"\n{'=' * 60}\n{label}\n{'=' * 60}")
    try:
        result = extract(pdf_path, out_dir, pages=TEST_PAGES, **EXTRACT_KWARGS)
    except Exception as e:
        print(f"FAILED: {e}")
        return

    tables = result.elements_by_type("table")
    print(f"Tables detected: {len(tables)}")
    for t in tables:
        print(
            f"  - page {t.get('page number')}: "
            f"{t.get('number of rows')} rows x {t.get('number of columns')} cols"
        )

    # Flag any paragraph blocks that look like a flattened table: long text with a
    # high density of digits (the failure signature we saw in native mode).
    suspects = []
    for p in result.elements_by_type("paragraph"):
        content = p.get("content", "")
        if len(content) > 150:
            digit_ratio = sum(c.isdigit() for c in content) / max(len(content), 1)
            if digit_ratio > 0.15:
                suspects.append((p.get("page number"), digit_ratio, content[:100]))
    print(f"Suspicious number-heavy paragraphs (likely flattened tables): {len(suspects)}")
    for page, ratio, preview in suspects:
        print(f"  - page {page} (digit ratio {ratio:.0%}): {preview}...")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python compare_native_vs_hybrid.py path/to/glenmark.pdf")
        sys.exit(1)

    pdf_path = Path(sys.argv[1])
    base_out = Path("data/extracted/diagnostic")

    EXTRACT_KWARGS = {}
    summarize("NATIVE (cluster mode, current default)", base_out / "native", pdf_path)

    EXTRACT_KWARGS = {"hybrid": True, "hybrid_backend": "docling-fast"}
    summarize("HYBRID — docling-fast backend", base_out / "hybrid_docling", pdf_path)

    print(
        "\nCompare the table counts and row/col shapes above against the source PDF "
        "(page 4 should show a table with ~6 rows x ~7 cols for the employee "
        "headcount breakdown). If hybrid detects it and native doesn't, hybrid is "
        "the path forward for numeric ESG tables — next step is deciding whether to "
        "route all pages through hybrid or only pages where native produces "
        "suspicious number-heavy paragraphs."
    )
