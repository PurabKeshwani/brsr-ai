"""
Ingestion Layer — Phase 1

Wraps OpenDataLoader PDF (github.com/opendataloader-project/opendataloader-pdf) to turn a
raw BRSR PDF into structured, machine-readable output: JSON with per-element bounding boxes
(needed later for the evidence-viewer UI) plus a clean Markdown rendering for downstream NLP.

Design notes:
- OpenDataLoader's *native* pipeline (used by default here) is deterministic/rule-based and
  needs no GPU — this is what makes local, laptop-only development of this module possible.
- Native cluster-mode table detection is border-based-plus-clustering and is known (from
  real-world testing against a Glenmark Pharma BRSR filing, Aug 2026) to miss borderless,
  whitespace-aligned numeric tables — the exact layout most BRSR ESG data tables use. The
  `hybrid=True` path routes through an AI-assisted backend instead, which is the next thing
  to validate against those same problem tables before deciding this is the production path.
- We deliberately extract BOTH json (bounding boxes, structure) and markdown (clean text for
  the NLP pipeline) in one call rather than parsing markdown out of the json ourselves.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import opendataloader_pdf as odl


class ExtractionError(RuntimeError):
    """Raised when OpenDataLoader fails to produce usable output for a given PDF."""


@dataclass
class ExtractionResult:
    source_pdf: Path
    markdown_path: Path
    json_path: Path
    markdown_text: str
    structured: dict
    # ^ Parsed OpenDataLoader JSON. Verified schema (v2.5.0): top-level keys include
    #   "number of pages" and "kids" — a list of elements (heading/paragraph/table/...),
    #   each with "type", "page number", "bounding box" [x0, y0, x1, y1], and "content".
    #   Tables additionally nest their own "rows". This is intentionally kept as raw dict
    #   rather than a typed model for now — we only need a handful of fields today, and
    #   locking in a full schema before we've seen real (messier) BRSR PDFs would be
    #   premature.

    @property
    def page_count(self) -> int:
        return self.structured.get("number of pages", 0)

    @property
    def elements(self) -> list[dict]:
        """Flat list of top-level structural elements (headings, paragraphs, tables, ...)."""
        return self.structured.get("kids", [])

    def elements_by_type(self, el_type: str) -> list[dict]:
        return [el for el in self.elements if el.get("type") == el_type]


def extract(
    pdf_path: str | Path,
    output_dir: str | Path,
    *,
    hybrid: bool = False,
    hybrid_backend: str = "hancom-ai",
    ocr_strategy: Optional[str] = None,
    pages: Optional[str] = None,
) -> ExtractionResult:
    """
    Extracts a single BRSR PDF into structured JSON + Markdown.

    Args:
        pdf_path: path to the source PDF.
        output_dir: directory to write <stem>.json / <stem>.md into.
        hybrid: if True, route through the AI-capable hybrid backend instead of the
            native rule-based pipeline. Requires an `opendataloader-pdf-hybrid` server
            already running locally (see README for setup).
        hybrid_backend: which hybrid backend to use. "docling-fast" is a general
            AI-assisted layout/table model; "hancom-ai" additionally supports the
            ocr_strategy option below. Only used when hybrid=True.
        ocr_strategy: only meaningful when hybrid_backend="hancom-ai". "force" forces
            OCR on every page; "auto" (default) OCRs only where the native text
            stream looks unreliable.
        pages: optional page range (e.g. "4,5,20-21") to restrict extraction to —
            useful for fast targeted testing of specific problem pages instead of
            re-running the full document, especially in hybrid mode which is much
            slower than the native pipeline.

    Returns:
        ExtractionResult with both the raw markdown text and parsed structured JSON
        loaded into memory, ready for the preprocessing stage (Phase 1, next module).

    Raises:
        ExtractionError: if OpenDataLoader produces no usable output for this PDF.
    """
    pdf_path = Path(pdf_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not pdf_path.exists():
        raise FileNotFoundError(f"No such PDF: {pdf_path}")

    convert_kwargs = dict(
        input_path=str(pdf_path),
        output_dir=str(output_dir),
        format=["json", "markdown"],
        quiet=True,
        reading_order="xycut",   # correct multi-column reading order — matters for BRSR layouts
        table_method="cluster",  # more robust than border-only detection on real-world tables
    )
    if pages:
        convert_kwargs["pages"] = pages
    if hybrid:
        convert_kwargs["hybrid"] = hybrid_backend
        if hybrid_backend == "hancom-ai":
            convert_kwargs["hybrid_hancom_ai_ocr_strategy"] = ocr_strategy or "auto"

    odl.convert(**convert_kwargs)

    odl.convert(**convert_kwargs)

    json_path = output_dir / f"{pdf_path.stem}.json"
    md_path = output_dir / f"{pdf_path.stem}.md"

    if not json_path.exists() or not md_path.exists():
        raise ExtractionError(
            f"OpenDataLoader did not produce expected output for {pdf_path.name} "
            f"(expected {json_path.name} and {md_path.name} in {output_dir})"
        )

    structured = json.loads(json_path.read_text(encoding="utf-8"))
    markdown_text = md_path.read_text(encoding="utf-8")

    return ExtractionResult(
        source_pdf=pdf_path,
        markdown_path=md_path,
        json_path=json_path,
        markdown_text=markdown_text,
        structured=structured,
    )
