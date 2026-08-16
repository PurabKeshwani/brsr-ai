import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ingestion.row_parser import (
    ReconciliationStatus,
    check_two_part_breakdown,
    extract_data_rows,
    split_into_rows,
    to_number,
)

GLENMARK_WELLBEING_PARAGRAPH = (
    "Permanent Employees Male 11,371 11,371 100% 11,371 100% N/A N/A 5,705 50% "
    "3,966 35% Female 941 941 100% 941 100% 941 100% N/A N/A 941 100% Total "
    "12,312 12,312 100% 12,312 100% 941 100% 5,705 50% 4,907 40% Other than "
    "Permanent Employees Male 326 326 100% 233 71% N/A N/A 12 4% 104 32% Female "
    "70 70 100% 65 93% 70 100% N/A N/A 7 10% Total 396 396 100% 298 75% 70 100% "
    "12 4% 111 28%"
)

AEQUS_WELLBEING_PARAGRAPH = (
    "Permanent employees Male 980 980 100% 980 100% NA NA 0 0% 0 0% Female 125 "
    "125 100% 125 100% 125 100% NA NA 125 100% Total 1105 1105 100% 1105 100% "
    "125 100%^ 0 0% 125 100%"
)


def test_glenmark_wellbeing_splits_into_six_correct_rows():
    rows = split_into_rows(GLENMARK_WELLBEING_PARAGRAPH, page=20)
    assert [r.label for r in rows] == [
        "Permanent Employees Male", "Female", "Total",
        "Other than Permanent Employees Male", "Female", "Total",
    ]
    assert rows[0].values == [
        "11,371", "11,371", "100%", "11,371", "100%", "N/A", "N/A",
        "5,705", "50%", "3,966", "35%",
    ]
    assert rows[2].values == [
        "12,312", "12,312", "100%", "12,312", "100%", "941", "100%",
        "5,705", "50%", "4,907", "40%",
    ]


def test_aequs_footnote_marker_does_not_break_row_split():
    rows = split_into_rows(AEQUS_WELLBEING_PARAGRAPH, page=14)
    assert [r.label for r in rows] == ["Permanent employees Male", "Female", "Total"]
    total_row = rows[2]
    assert total_row.values == [
        "1105", "1105", "100%", "1105", "100%", "125", "100%", "0", "0%", "125", "100%",
    ]
    assert total_row.footnotes == ["100%^"]


def test_check_two_part_breakdown_fits_for_min_wage_shape():
    result = check_two_part_breakdown(["1105", "471", "43%", "634", "57%"])
    assert result.status == ReconciliationStatus.FITS


def test_check_two_part_breakdown_mismatches_for_wellbeing_shape():
    result = check_two_part_breakdown(["11,371", "11,371", "100%", "11,371", "100%"])
    assert result.status == ReconciliationStatus.MISMATCH


def test_check_two_part_breakdown_skips_on_na():
    result = check_two_part_breakdown(["396", "N/A", "-", "233", "71%"])
    assert result.status == ReconciliationStatus.SKIPPED


def test_to_number_handles_na_and_commas_and_percent():
    assert to_number("N/A") is None
    assert to_number("NIL") is None
    assert to_number("11,371") == 11371.0
    assert to_number("43%") == 43.0


def test_extract_data_rows_walks_nested_json_tree():
    tree = {
        "kids": [
            {"type": "paragraph", "page number": 20, "content": GLENMARK_WELLBEING_PARAGRAPH},
            {"type": "list", "kids": [
                {"type": "list item", "page number": 14, "content": AEQUS_WELLBEING_PARAGRAPH},
            ]},
        ]
    }
    rows = extract_data_rows(tree)
    assert len(rows) == 9
    assert rows[0].page == 20
    assert rows[-1].page == 14


def test_narrative_prose_with_one_number_is_not_treated_as_data_row():
    tree = {
        "kids": [
            {"type": "paragraph", "page number": 3, "content": (
                "The Company's primary products and services, accounting "
                "for 90% of its turnover, include research and development."
            )}
        ]
    }
    rows = extract_data_rows(tree)
    assert rows == []


def test_column_header_fragment_does_not_overwrite_real_context():
    tree = {
        "kids": [
            {"type": "heading", "page number": 20,
             "content": "1. a. Details of measures for the well-being of employees:"},
            {"type": "paragraph", "page number": 20, "content": "% (D/A)"},
            {"type": "paragraph", "page number": 20, "content": "No. (B) % (B/A)"},
            {"type": "paragraph", "page number": 20,
             "content": "Male 980 980 100% 980 100% NA NA 0 0% 0 0%"},
        ]
    }
    rows = extract_data_rows(tree)
    assert len(rows) == 1
    assert "well-being of employees" in rows[0].context.lower()


def test_real_question_stored_as_caption_type_is_recognized():
    tree = {
        "kids": [
            {"type": "heading", "page number": 20,
             "content": "Principle 3: Businesses should respect and promote the well-being of all employees, including those in their value chains. Essential Indicators"},
            {"type": "caption", "page number": 20,
             "content": "1. a. Details of measures for the well-being of employees:"},
            {"type": "paragraph", "page number": 20,
             "content": "Male 980 980 100% 980 100% NA NA 0 0% 0 0%"},
        ]
    }
    rows = extract_data_rows(tree)
    assert len(rows) == 1
    assert rows[0].context == "1. a. Details of measures for the well-being of employees:"


def test_short_section_sub_label_does_not_overwrite_real_context():
    tree = {
        "kids": [
            {"type": "paragraph", "page number": 28,
             "content": "2. Details of minimum wages paid to employees and workers, in the following format"},
            {"type": "heading", "page number": 28, "content": "Other than Permanent"},
            {"type": "paragraph", "page number": 28,
             "content": "Male 326 146 45% 180 55% 241 132 55% 109 45%"},
        ]
    }
    rows = extract_data_rows(tree)
    assert len(rows) == 1
    assert "minimum wages" in rows[0].context.lower()


def test_section_label_does_not_overwrite_real_context():
    tree = {
        "kids": [
            {"type": "paragraph", "page number": 28,
             "content": "2. Details of minimum wages paid to employees and workers, in the following format"},
            {"type": "paragraph", "page number": 28, "content": "Employees Permanent"},
            {"type": "paragraph", "page number": 28,
             "content": "Permanent 12,312 3 0.02% 12,309 99.98%"},
        ]
    }
    rows = extract_data_rows(tree)
    assert len(rows) == 1
    assert "minimum wages" in rows[0].context.lower()


def test_question_nested_inside_list_items_key_is_found():
    tree = {
        "kids": [
            {"type": "heading", "page number": 20,
             "content": "Principle 3: Businesses should respect and promote the well-being of all employees, including those in their value chains. Essential Indicators"},
            {"type": "list", "page number": 20, "list items": [
                {"type": "list item", "page number": 20,
                 "content": "1. a. Details of measures for the well-being of employees:"},
            ]},
            {"type": "paragraph", "page number": 20,
             "content": "Male 980 980 100% 980 100% NA NA 0 0% 0 0%"},
        ]
    }
    rows = extract_data_rows(tree)
    assert len(rows) == 1
    assert rows[0].context == "1. a. Details of measures for the well-being of employees:"


def test_data_row_nested_three_levels_inside_list_items_is_found():
    tree = {
        "kids": [
            {"type": "paragraph", "page number": 20,
             "content": "b. Details of measures for the well-being of workers:"},
            {"type": "list", "page number": 20, "list items": [
                {
                    "type": "list item", "page number": 20,
                    "content": "Male 640 640 100% 640 100% NA NA 640 100% 640 100%",
                    "kids": [
                        {"type": "list", "page number": 20, "list items": [
                            {"type": "list item", "page number": 20,
                             "content": "Total 661 661 100% 661 100% 75 100% 1941 100% 2016 100%"},
                        ]}
                    ],
                }
            ]},
        ]
    }
    rows = extract_data_rows(tree)
    assert len(rows) == 2
    assert rows[0].label == "Male"
    assert rows[1].label == "Total"
    assert all("well-being of workers" in r.context.lower() for r in rows)


def test_numbered_question_without_trailing_period_is_recognized():
    tree = {
        "kids": [
            {"type": "list item", "page number": 22,
             "content": "6. Is there a mechanism available to receive and redress grievances for employees and workers:"},
            {"type": "list", "page number": 22, "list items": [
                {
                    "type": "list item", "page number": 22,
                    "content": "7 Membership of employees and workers in association(s) or Unions recognized by the listed entity:",
                    "kids": [
                        {"type": "paragraph", "page number": 22,
                         "content": "12,312 0 0 11,641 242 2%"},
                    ],
                },
                {
                    "type": "list item", "page number": 22,
                    "content": "8 Details of training given to employees and workers:",
                    "kids": [
                        {"type": "paragraph", "page number": 22,
                         "content": "Employees Male 11,371 10,854 95% 10,911 96% 10,775 10,775 100% 9,933 92%"},
                    ],
                },
            ]},
        ]
    }
    rows = extract_data_rows(tree)
    assert len(rows) == 2

    union_row = rows[0]
    assert "membership" in union_row.context.lower()
    assert "grievances" not in union_row.context.lower()

    training_row = rows[1]
    assert "details of training" in training_row.context.lower()
    assert "membership" not in training_row.context.lower()


def test_two_value_isolated_paragraph_is_captured_not_silently_dropped():
    # Reproduces the real Glenmark bug: a legitimate 2-value table
    # ("Gross wages paid to females...") was being silently discarded
    # before MIN_VALUE_TOKENS_FOR_CANDIDATE was lowered from 4 to 2,
    # because "2025-26"/"2024-25" don't count as value tokens (the
    # hyphen doesn't match VALUE_RE) and only 2 real values remained.
    tree = {
        "kids": [
            {"type": "heading", "page number": 41,
             "content": "Gross wages paid to females as % of total wages paid by the entity, in the following format:"},
            {"type": "paragraph", "page number": 41,
             "content": "FY 2025-26 FY 2024-25 Gross wages paid to females as % of total wages 10.23% 9.40%"},
        ]
    }
    rows = extract_data_rows(tree)
    assert len(rows) == 1
    assert rows[0].values == ["10.23%", "9.40%"]


def test_question_ending_in_colon_with_incidental_numbers_is_not_misread_as_data():
    # Reproduces the real Glenmark regression: "22. Turnover rate..." has
    # two incidental digit-like tokens ("22.", "3") that cross the lowered
    # MIN_VALUE_TOKENS_FOR_CANDIDATE=2 threshold — must still be recognized
    # as a question (ends with ":"), not misread as a 2-value data row.
    tree = {
        "kids": [
            {"type": "heading", "page number": 4,
             "content": "21. Representation of women:"},
            {"type": "paragraph", "page number": 4, "content": "Board of Directors 9 5 56%"},
            {"type": "paragraph", "page number": 4,
             "content": "22. Turnover rate for permanent employees and workers (Disclose trends for the past 3 years):"},
            {"type": "paragraph", "page number": 4,
             "content": "Permanent Employees 16% 16% 16% 15% 17% 15% 18% 19% 18%"},
        ]
    }
    rows = extract_data_rows(tree)
    turnover_row = [r for r in rows if len(r.values) == 9][0]
    assert "turnover rate" in turnover_row.context.lower()
    assert "representation of women" not in turnover_row.context.lower()


def test_numbered_data_row_not_ending_in_colon_still_extracted_as_data():
    # Confirms the fix doesn't over-correct: a real numbered data row
    # ("1. Permanent (D)...") also matches the numbered-question pattern,
    # but does NOT end with ":" — must remain classified as data.
    tree = {
        "kids": [
            {"type": "heading", "page number": 4,
             "content": "a. Employees and workers (including differently abled):"},
            {"type": "paragraph", "page number": 4,
             "content": "1. Permanent (D) 12,312 11,371 92% 941 8%"},
        ]
    }
    rows = extract_data_rows(tree)
    assert len(rows) == 1
    assert rows[0].values == ["12,312", "11,371", "92%", "941", "8%"]

def test_rupee_symbol_as_separate_token_does_not_corrupt_row_split():
    # Reproduces the real Glenmark bug: "₹" appears as its own token before
    # the number ("₹ 4,96,55,753"), which used to be neither a value nor
    # cleanly a label word, corrupting row boundaries. Real source content
    # from Glenmark page 29's median remuneration table.
    content = (
        "Board of Directors (BoD) 4 ₹ 4,96,55,753 5 ₹ 18,00,000 "
        "Key Management Personnel 3 ₹ 74,86,735 1 ₹ 0"
    )
    rows = split_into_rows(content, page=29)
    assert rows[0].label == "Board of Directors (BoD)"
    assert rows[0].values == ["4", "₹4,96,55,753", "5", "₹18,00,000"]
    assert rows[1].label == "Key Management Personnel"
    assert rows[1].values == ["3", "₹74,86,735", "1", "₹0"]

def test_yes_no_categorical_tokens_do_not_fragment_a_row():
    # Reconstructed from the real fragmentation pattern confirmed on BOTH
    # companies' retirement_benefits data: "PF"/"ESI" rows broke into
    # multiple 2-value fragments plus a stray "Yes"-labeled row, because
    # "Yes"/"Y" (the authority-deduction column's real answer) wasn't
    # recognized as a value token. Glenmark's Gratuity row happened to use
    # "N/A" in that slot instead and worked correctly even before this fix
    # — confirming Yes/Y specifically was the missing piece.
    content = "PF 100% 100% Yes 100% 100% Yes ESI 100% 100% Yes 100% 100% Yes"
    rows = split_into_rows(content, page=21)
    assert len(rows) == 2
    assert rows[0].label == "PF"
    assert rows[0].values == ["100%", "100%", "Yes", "100%", "100%", "Yes"]
    assert rows[1].label == "ESI"
    assert rows[1].values == ["100%", "100%", "Yes", "100%", "100%", "Yes"]