"""
Runs the complete analysis suite (trends, consistency, assurance,
greenwashing signals, silent removal) against a single company's latest
ingested filing, and prints a readable report.

This is the cross-company validation harness — the same checks that were
built and verified against NIIT are run here against any other ingested
company, to confirm they generalize rather than being accidentally tuned
to NIIT's specific filing quirks.

Usage:
    python scripts/run_full_analysis.py "Mastek"
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from analysis.assurance import get_assurance_profile
from analysis.consistency import CheckStatus, run_all_consistency_checks
from analysis.greenwashing import find_claim_evidence_signals
from analysis.queries import get_company_by_name, get_latest_filing
from analysis.silent_removal import find_silently_removed_metrics
from analysis.trends import get_trend
from db.session import get_session, init_db

KEY_TRENDS = [
    "TotalScope1Emissions", "TotalScope2Emissions", "TotalScope3Emissions",
    "TotalWasteGenerated", "TotalVolumeOfWaterWithdrawal",
    "TotalEnergyConsumedFromRenewableAndNonRenewableSources",
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("company_hint", help="Partial company name to search for")
    args = ap.parse_args()

    init_db()
    with get_session() as session:
        company = get_company_by_name(session, args.company_hint)
        if company is None:
            print(f"No company found matching {args.company_hint!r}. Ingest it first with scripts/ingest_company.py")
            sys.exit(1)

        filing = get_latest_filing(session, company.id)
        print(f"=== {company.name} (CIN: {company.cin}) ===")
        print(f"Filing: FY {filing.financial_year_start} to {filing.financial_year_end}")
        print(f"Total facts: {filing.raw_fact_count}\n")

        print("--- Key metric trends ---")
        for concept in KEY_TRENDS:
            trend = get_trend(session, filing.id, concept)
            if trend.direction == "insufficient_data":
                print(f"  {concept}: (no multi-year data found)")
            else:
                print(f"  {concept}: {trend.previous_value} -> {trend.latest_value}  "
                      f"({trend.direction}, {trend.yoy_change_pct}%)")

        print("\n--- Internal consistency checks ---")
        results = run_all_consistency_checks(session, filing.id)
        passed = sum(1 for r in results if r.status == CheckStatus.PASS)
        failed = [r for r in results if r.status == CheckStatus.FAIL]
        skipped = sum(1 for r in results if r.status == CheckStatus.SKIP)
        print(f"  Total checks: {len(results)}  |  Pass: {passed}  |  Fail: {len(failed)}  |  Skip: {skipped}")
        for r in failed[:10]:
            print(f"  FAIL: {r.concept} [{r.context_key}] — {r.message}")
        if len(failed) > 10:
            print(f"  ... and {len(failed) - 10} more failures")

        print("\n--- Assurance profile ---")
        profile = get_assurance_profile(session, filing.id)
        print(f"  Disclosure areas found: {profile.total_disclosure_areas}")
        print(f"  Assured: {profile.assured_count}  (Reasonable: {profile.reasonable_count}, Limited: {profile.limited_count})")
        print(f"  Assured but level unresolved: {profile.assured_but_level_unresolved_count}")
        print(f"  Unassured: {profile.unassured_count}")
        print(f"  Reasonable-assurance %: {profile.reasonable_assurance_pct}%")

        print("\n--- Greenwashing signals (claim vs evidence) ---")
        signals = find_claim_evidence_signals(session, filing.id)
        if not signals:
            print("  None found.")
        for s in signals:
            print(f"  [{s.severity.value}] {s.concept}")
            print(f"    Sentence: {s.matched_sentence}")
            print(f"    Trend: {s.trend.previous_value} -> {s.trend.latest_value} ({s.trend.yoy_change_pct}%)")

        print("\n--- Silent removal flags ---")
        removed = find_silently_removed_metrics(session, filing.id)
        print(f"  Found: {len(removed)}")
        for r in removed[:15]:
            print(f"  {r.concept} [{r.dimensions_key}] — was {r.prior_year_value!r} in {r.prior_year_period}")
        if len(removed) > 15:
            print(f"  ... and {len(removed) - 15} more")


if __name__ == "__main__":
    main()