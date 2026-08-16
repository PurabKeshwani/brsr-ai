import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ingestion.field_mapper import ExtractionStatus, map_row
from ingestion.row_parser import DataRow
from ingestion.schema_registry import load_registry

REGISTRY = load_registry()


def test_employee_worker_headcount_accepts_with_passing_validation():
    row = DataRow(
        page=4, label="Total employees (D + E)",
        values=["12,708", "11,697", "92%", "1,011", "8%"],
        context="a. Employees and workers (including differently abled)",
    )
    mapped = map_row(row, REGISTRY)
    assert mapped.status == ExtractionStatus.ACCEPT
    assert mapped.family_id == "employee_worker_headcount"
    assert mapped.fields["total"] == "12,708"


def test_differently_abled_vs_headcount_never_cross_match():
    diff_abled_row = DataRow(page=4, label="x", values=["68", "56", "82%", "12", "18%"], context="b. Differently abled Employees and workers")
    headcount_row = DataRow(page=4, label="x", values=["1", "1", "1%", "1", "1%"], context="a. Employees and workers (including differently abled)")
    assert map_row(diff_abled_row, REGISTRY).family_id == "differently_abled_headcount"
    assert map_row(headcount_row, REGISTRY).family_id == "employee_worker_headcount"


def test_aequs_style_allcaps_label_still_maps_to_differently_abled():
    row = DataRow(page=3, label="Permanent (D)", values=["0", "0", "0%", "0", "0%"], context="DIFFERENTLY ABLED EMPLOYEES")
    assert map_row(row, REGISTRY).family_id == "differently_abled_headcount"


def test_minimum_wages_10_value_shape_accepts():
    row = DataRow(
        page=28, label="Permanent",
        values=["12,312", "3", "0.02%", "12,309", "99.98%", "11,641", "252", "2%", "11,389", "98%"],
        context="2. Details of minimum wages paid to employees and workers, in the following format",
    )
    mapped = map_row(row, REGISTRY)
    assert mapped.status == ExtractionStatus.ACCEPT
    assert mapped.family_id == "minimum_wages"


def test_unmapped_context_abstains_with_reason_unmapped():
    row = DataRow(page=1, label="", values=["400", "099", "91", "22"], context="")
    mapped = map_row(row, REGISTRY)
    assert mapped.status == ExtractionStatus.ABSTAIN
    assert mapped.reason == "unmapped"


def test_shape_mismatch_abstains_distinctly_from_unmapped():
    row = DataRow(
        page=99, label="broken", values=["1", "2", "3"],
        context="2. Details of minimum wages paid to employees and workers, in the following format",
    )
    mapped = map_row(row, REGISTRY)
    assert mapped.status == ExtractionStatus.ABSTAIN
    assert mapped.reason == "shape_mismatch"
    # family_id is tagged _SHAPE_MISMATCH (not plain "minimum_wages") since
    # map_row now tries every context-matching family before giving up —
    # the suffix makes clear which family it was closest to, useful when
    # multiple families share a context pattern (e.g. air_emissions vs
    # air_emissions_with_blank_unit).
    assert mapped.family_id == "minimum_wages_SHAPE_MISMATCH"


def test_validation_failure_abstains_distinctly_and_keeps_fields():
    row = DataRow(
        page=4, label="broken_math", values=["100", "10", "10%", "10", "10%"],
        context="a. Employees and workers (including differently abled)",
    )
    mapped = map_row(row, REGISTRY)
    assert mapped.status == ExtractionStatus.ABSTAIN
    assert mapped.reason == "validation_failed"
    assert mapped.fields["total"] == "100"


def test_provenance_carries_sebi_metadata():
    row = DataRow(
        page=28, label="x",
        values=["12,312", "3", "0.02%", "12,309", "99.98%", "11,641", "252", "2%", "11,389", "98%"],
        context="2. Details of minimum wages paid to employees and workers, in the following format",
    )
    mapped = map_row(row, REGISTRY)
    assert mapped.provenance.section == "C"
    assert mapped.provenance.principle == 5
    assert mapped.provenance.disclosure_question_id == "2"


def test_locations_summary_accepts_with_validation():
    row = DataRow(
        page=3, label="National", values=["8", "19", "27"],
        context="18. Number of locations where plants and/or operations/offices of the entity are situated:",
    )
    mapped = map_row(row, REGISTRY)
    assert mapped.status == ExtractionStatus.ACCEPT
    assert mapped.family_id == "locations_summary"


def test_gross_wages_accepts():
    row = DataRow(
        page=29, label="Gross wages paid to females as % of total wages",
        values=["10.23%", "9.40%"],
        context="b. Gross wages paid to females as % of total wages paid by the entity:",
    )
    mapped = map_row(row, REGISTRY)
    assert mapped.status == ExtractionStatus.ACCEPT
    assert mapped.family_id == "gross_wages_female_pct"


def test_posh_shared_context_binds_generically_label_disambiguates():
    pct_row = DataRow(
        page=30, label="Complaints on POSH as a % of female employee/ workers",
        values=["0.61%", "0.44%"],
        context="7. Complaints filed under the Sexual Harassment of Women at Workplace (Prevention, Prohibition and Redressal) Act, 2013:",
    )
    upheld_row = DataRow(
        page=30, label="Complaints on POSH upheld",
        values=["8", "4"],
        context="7. Complaints filed under the Sexual Harassment of Women at Workplace (Prevention, Prohibition and Redressal) Act, 2013:",
    )
    mapped_pct = map_row(pct_row, REGISTRY)
    mapped_upheld = map_row(upheld_row, REGISTRY)
    assert mapped_pct.family_id == mapped_upheld.family_id == "posh_and_shw_act_metrics"
    assert mapped_pct.row.label != mapped_upheld.row.label


def test_wellbeing_spending_accepts_and_no_longer_cross_matches_coverage():
    # Reproduces the real Glenmark shape_mismatch that led to this fix:
    # Q1.c ("Spending on measures towards well-being...") used to
    # incorrectly match wellbeing_coverage_employees's old, too-broad
    # pattern. Now it must match its own dedicated family.
    row = DataRow(
        page=21, label="",
        values=["0.16%", "0.19%"],
        context="c. Spending on measures towards well-being of employees and workers (including permanent and other than permanent) in the following format:",
    )
    mapped = map_row(row, REGISTRY)
    assert mapped.status == ExtractionStatus.ACCEPT
    assert mapped.family_id == "wellbeing_spending_pct"
    assert mapped.family_id != "wellbeing_coverage_employees"


def test_wellbeing_coverage_employees_still_matches_real_question_after_tightening():
    row = DataRow(
        page=20, label="Male",
        values=["11,371", "11,371", "100%", "11,371", "100%", "N/A", "N/A", "5,705", "50%", "3,966", "35%"],
        context="1. a. Details of measures for the well-being of employees:",
    )
    mapped = map_row(row, REGISTRY)
    assert mapped.status == ExtractionStatus.ACCEPT
    assert mapped.family_id == "wellbeing_coverage_employees"

def test_energy_consumption_accepts_generic_shape():
    row = DataRow(
        page=32, label="Total electricity consumption (A)",
        values=["46,951", "16,602"],
        context="1. Details of total energy consumption and energy intensity:",
    )
    mapped = map_row(row, REGISTRY)
    assert mapped.status == ExtractionStatus.ACCEPT
    assert mapped.family_id == "energy_consumption"
    assert mapped.fields["current_fy_value"] == "46,951"


def test_energy_consumption_second_verified_row_also_accepts():
    row = DataRow(
        page=32, label="From non-renewable sources Total electricity consumption (D)",
        values=["3,71,005", "3,77,263"],
        context="1. Details of total energy consumption and energy intensity:",
    )
    mapped = map_row(row, REGISTRY)
    assert mapped.status == ExtractionStatus.ACCEPT
    assert mapped.fields["current_fy_value"] == "3,71,005"

def test_water_disclosures_and_water_stress_never_cross_match():
    # Real evidence: near-identical row labels, genuinely different scope
    # and different real values (company-wide vs water-stress-area-only).
    company_wide_row = DataRow(
        page=33, label="Total volume of water withdrawal (in kilolitres) (i + ii + iii + iv + v)",
        values=["5,46,033", "5,29,632"],
        context="3. Provide details of the following disclosures related to water:",
    )
    water_stress_row = DataRow(
        page=37, label="Total volume of water withdrawal (in kilolitres)",
        values=["1,04,684", "1,02,606"],
        context="1. Water withdrawal, consumption and discharge in areas of water stress (in kilolitres):",
    )
    mapped_company = map_row(company_wide_row, REGISTRY)
    mapped_stress = map_row(water_stress_row, REGISTRY)

    assert mapped_company.family_id == "water_disclosures"
    assert mapped_stress.family_id == "water_stress_area_disclosures"
    assert mapped_company.family_id != mapped_stress.family_id
    assert mapped_company.status == mapped_stress.status == ExtractionStatus.ACCEPT

def test_waste_management_accepts():
    row = DataRow(
        page=35, label="Total Waste Generated (A+ B + C + D + E + F + G + H)",
        values=["4,060", "3,808"],
        context="9. Provide details related to waste management by the entity:",
    )
    mapped = map_row(row, REGISTRY)
    assert mapped.status == ExtractionStatus.ACCEPT
    assert mapped.family_id == "waste_management"

def test_ghg_emissions_accepts_even_with_empty_label():
    row = DataRow(
        page=34, label="",
        values=["11,797", "17,263"],
        context="7. Provide details of greenhouse gas emissions (Scope 1 and Scope 2 emissions) and its intensity:",
    )
    mapped = map_row(row, REGISTRY)
    assert mapped.status == ExtractionStatus.ACCEPT
    assert mapped.family_id == "ghg_emissions"

def test_air_emissions_accepts_and_distinct_from_ghg():
    row = DataRow(
        page=34, label="Parameter Unit FY 2025-26 FY 2024-25 NOx MT",
        values=["118", "120"],
        context="6. Please provide details of air emissions (other than GHG emissions) by the entity:",
    )
    mapped = map_row(row, REGISTRY)
    assert mapped.status == ExtractionStatus.ACCEPT
    assert mapped.family_id == "air_emissions"
    assert mapped.family_id != "ghg_emissions"

def test_air_emissions_blank_unit_variant_accepts_where_2value_would_mismatch():
    row = DataRow(
        page=34, label="Persistent organic pollutants (POP)",
        values=["-", "N/A", "N/A"],
        context="6. Please provide details of air emissions (other than GHG emissions) by the entity:",
    )
    mapped = map_row(row, REGISTRY)
    assert mapped.status == ExtractionStatus.ACCEPT
    assert mapped.family_id == "air_emissions_with_blank_unit"
    assert mapped.fields["unit_placeholder"] == "-"


def test_air_emissions_2value_variant_still_works_after_multi_shape_change():
    row = DataRow(
        page=34, label="Parameter Unit FY 2025-26 FY 2024-25 NOx MT",
        values=["118", "120"],
        context="6. Please provide details of air emissions (other than GHG emissions) by the entity:",
    )
    mapped = map_row(row, REGISTRY)
    assert mapped.status == ExtractionStatus.ACCEPT
    assert mapped.family_id == "air_emissions"


def test_waste_management_blank_unit_variant_accepts():
    row = DataRow(
        page=26, label="Radioactive waste (F)",
        values=["-", "0.00", "0.00"],
        context="9. Provide details related to waste management by the entity, in the following format:",
    )
    mapped = map_row(row, REGISTRY)
    assert mapped.status == ExtractionStatus.ACCEPT
    assert mapped.family_id == "waste_management_with_blank_unit"


def test_genuinely_unmatchable_shape_still_reports_shape_mismatch():
    # Confirms multi-shape trying doesn't silently swallow real mismatches.
    row = DataRow(
        page=99, label="broken", values=["1", "2", "3", "4", "5", "6", "7"],
        context="6. Please provide details of air emissions (other than GHG emissions) by the entity:",
    )
    mapped = map_row(row, REGISTRY)
    assert mapped.status == ExtractionStatus.ABSTAIN
    assert mapped.reason == "shape_mismatch"


def test_accounts_payable_days_accepts():
    row = DataRow(
        page=17, label="FY 2025-26 FY 2024-25 Number of days of accounts payable",
        values=["292", "275"],
        context="8. Number of days of accounts payables ((Accounts payable *365) / Cost of goods/services procured) in the following format:",
    )
    mapped = map_row(row, REGISTRY)
    assert mapped.status == ExtractionStatus.ACCEPT
    assert mapped.family_id == "accounts_payable_days"


def test_rd_capex_pct_accepts_both_rows_same_context():
    rd_row = DataRow(
        page=18, label="R&D", values=["100%", "100%"],
        context="1. Percentage of R&D and capital expenditure (capex) investments in specific technologies to improve the environmental and social impacts of product and processes to total R&D and capex investments made by the entity, respectively:",
    )
    capex_row = DataRow(
        page=18, label="Capex", values=["0.06%", "0.02%"],
        context="1. Percentage of R&D and capital expenditure (capex) investments in specific technologies to improve the environmental and social impacts of product and processes to total R&D and capex investments made by the entity, respectively:",
    )
    assert map_row(rd_row, REGISTRY).family_id == "rd_capex_pct"
    assert map_row(capex_row, REGISTRY).family_id == "rd_capex_pct"


def test_retirement_benefits_accepts_with_specific_fields():
    row = DataRow(
        page=21, label="Yes Gratuity",
        values=["100%", "100%", "N/A", "100%", "100%", "N/A"],
        context="2. Details of retirement benefits, for Current FY and Previous Financial Year:",
    )
    mapped = map_row(row, REGISTRY)
    assert mapped.status == ExtractionStatus.ACCEPT
    assert mapped.family_id == "retirement_benefits"
    assert mapped.fields["current_fy_employee_coverage_pct"] == "100%"

def test_safety_incidents_accepts():
    row = DataRow(
        page=25, label="Employees", values=["0.43", "0.51"],
        context="11 Details of safety related incidents, in the following format:",
    )
    mapped = map_row(row, REGISTRY)
    assert mapped.status == ExtractionStatus.ACCEPT
    assert mapped.family_id == "safety_incidents"