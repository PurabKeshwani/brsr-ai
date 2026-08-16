import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest
from ingestion.extractor import extract, ExtractionError

FIXTURE_PDF = Path(__file__).parent / "fixtures" / "synthetic_brsr_sample.pdf"


@pytest.fixture(scope="module")
def result(tmp_path_factory):
    if not FIXTURE_PDF.exists():
        pytest.skip("Synthetic fixture PDF not generated yet — run make_synthetic_brsr_pdf.py")
    out_dir = tmp_path_factory.mktemp("extracted")
    return extract(FIXTURE_PDF, out_dir)


def test_extracts_correct_page_count(result):
    assert result.page_count == 1


def test_markdown_contains_expected_headings(result):
    assert "Principle 6" in result.markdown_text
    assert "Principle 3" in result.markdown_text


def test_markdown_preserves_table_as_markdown_table(result):
    assert "Scope 1 Emissions" in result.markdown_text
    assert "12,450" in result.markdown_text


def test_structured_json_has_bounding_boxes(result):
    headings = result.elements_by_type("heading")
    assert len(headings) >= 1
    for h in headings:
        assert "bounding box" in h
        assert len(h["bounding box"]) == 4


def test_structured_json_extracts_table_rows(result):
    tables = result.elements_by_type("table")
    assert len(tables) == 1
    assert tables[0]["number of rows"] == 4
    assert tables[0]["number of columns"] == 4


def test_missing_pdf_raises_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        extract(tmp_path / "does_not_exist.pdf", tmp_path)
