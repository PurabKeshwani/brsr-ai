"""
One-time migration: adds a "canonical_phrases" key to every family already
in schema_registry.json, using the exact real context strings we've
hand-verified across this project. ADDITIVE ONLY — never touches
field_names, validation_rules, or context_patterns, so the already-tested
regex-matching behavior is completely unaffected.

Run once:
    python scripts/add_canonical_phrases.py
"""
import json
from pathlib import Path

REGISTRY_PATH = Path(__file__).resolve().parents[1] / "src" / "ingestion" / "schema_registry.json"

# Real, hand-verified context strings from this project's conversation
# history — one representative phrase per family, used as the seed
# embedding for semantic matching.
CANONICAL_PHRASES = {
    "differently_abled_headcount": ["b. Differently abled Employees and workers", "DIFFERENTLY ABLED EMPLOYEES"],
    "employee_worker_headcount": ["a. Employees and workers (including differently abled)"],
    "representation_of_women": ["21. Representation of women"],
    "turnover_rate_3yr": ["Turnover rate for permanent employees and workers, disclose trends for the past 3 years"],
    "wellbeing_coverage_employees": ["Details of measures for the well-being of employees"],
    "wellbeing_coverage_workers": ["Details of measures for the well-being of workers"],
    "wellbeing_spending_pct": ["Spending on measures towards well-being of employees and workers"],
    "minimum_wages": ["Details of minimum wages paid to employees and workers"],
    "union_membership": ["Membership of employees and workers in association(s) or Unions recognized by the listed entity"],
    "training_coverage": ["Details of training given to employees and workers"],
    "locations_summary": ["Number of locations where plants and/or operations/offices of the entity are situated"],
    "gross_wages_female_pct": ["Gross wages paid to females as % of total wages paid by the entity"],
    "posh_and_shw_act_metrics": ["Complaints filed under the Sexual Harassment of Women at Workplace Act, 2013"],
    "energy_consumption": ["Details of total energy consumption and energy intensity"],
    "water_disclosures": ["Provide details of the following disclosures related to water"],
    "water_stress_area_disclosures": ["Water withdrawal, consumption and discharge in areas of water stress"],
    "waste_management": ["Provide details related to waste management by the entity"],
    "waste_management_with_blank_unit": ["Provide details related to waste management by the entity"],
    "ghg_emissions": ["Provide details of greenhouse gas emissions, Scope 1 and Scope 2 emissions, and its intensity"],
    "air_emissions": ["Please provide details of air emissions other than GHG emissions by the entity"],
    "air_emissions_with_blank_unit": ["Please provide details of air emissions other than GHG emissions by the entity"],
    "accounts_payable_days": ["Number of days of accounts payables"],
    "rd_capex_pct": ["Percentage of R&D and capital expenditure investments in specific technologies"],
    "retirement_benefits": ["Details of retirement benefits, for Current FY and Previous Financial Year"],
    "safety_incidents": ["Details of safety related incidents"],
}


def main():
    data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    updated, skipped = 0, 0

    for family in data["families"]:
        fid = family["family_id"]
        if fid in CANONICAL_PHRASES:
            family["canonical_phrases"] = CANONICAL_PHRASES[fid]
            updated += 1
        else:
            print(f"WARNING: no canonical phrase mapped for '{fid}' — skipped, semantic matching won't cover it yet")
            skipped += 1

    REGISTRY_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nUpdated {updated} families, skipped {skipped}. Registry written back to {REGISTRY_PATH}")


if __name__ == "__main__":
    main()