"""
Extracts a page range from a PDF into a new, smaller PDF — used to test
tools (like Docling's VLM pipeline) quickly on a known problem page
instead of processing the whole document.

Usage:
    python scripts/extract_pages.py data/raw_pdfs/glenmark.pdf 20 21 data/raw_pdfs/glenmark_p20-21.pdf
"""
import sys
from pypdf import PdfReader, PdfWriter

if __name__ == "__main__":
    if len(sys.argv) != 5:
        print("Usage: python extract_pages.py input.pdf start_page end_page output.pdf")
        sys.exit(1)

    input_path, start, end, output_path = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
    reader = PdfReader(input_path)
    writer = PdfWriter()
    for i in range(start - 1, end):  # human page numbers are 1-indexed
        writer.add_page(reader.pages[i])
    with open(output_path, "wb") as f:
        writer.write(f)
    print(f"Wrote pages {start}-{end} to {output_path}")