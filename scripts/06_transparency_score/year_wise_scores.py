"""
Year-wise Transparency Score (time series).

Computes the Transparency Score separately for EVERY filing of a company, so
the same company can be compared across financial years.

Place this file in:  scripts/06_transparency_score/year_wise_scores.py

Usage (run from the project root, with the venv active):
    python scripts/06_transparency_score/year_wise_scores.py
        -> every company that has 2 or more filings in the database
    python scripts/06_transparency_score/year_wise_scores.py --company "Sudarshan Chemical"
        -> only companies whose name contains this text
    python scripts/06_transparency_score/year_wise_scores.py --company "Jindal Stainless" --min-filings 1

Output: data/analysis/year_wise_scores.csv  (+ a compact table printed on screen)

Note: the Completeness concept universe is computed ONCE and reused for all
filings, so scores of different years are directly comparable.
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from analysis.scoring.completeness_score import get_concept_universe  # noqa: E402
from analysis.scoring.transparency_score import get_transparency_score  # noqa: E402
from db.models import Company  # noqa: E402
from db.session import get_session  # noqa: E402

OUT_PATH = Path("data/analysis/year_wise_scores.csv")


def fy_label(start: str, end: str) -> str:
    """'2025-04-01','2026-03-31' -> 'FY2025-26'. Calendar-year filings -> 'FYE 2025-12-31'."""
    if start[:4] != end[:4]:
        return f"FY{start[:4]}-{end[2:4]}"
    return f"FYE {end}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--company", default=None, help="company name contains this text (case-insensitive)")
    ap.add_argument("--min-filings", type=int, default=2, help="skip companies with fewer filings (default 2)")
    ap.add_argument("--out", default=str(OUT_PATH))
    args = ap.parse_args()

    rows = []
    with get_session() as session:
        universe = get_concept_universe(session)
        q = session.query(Company)
        if args.company:
            q = q.filter(Company.name.ilike(f"%{args.company}%"))

        for company in q.order_by(Company.name):
            filings = sorted(company.filings, key=lambda f: f.financial_year_end)
            if len(filings) < args.min_filings:
                continue
            for f in filings:
                r = get_transparency_score(session, f.id, concept_universe=universe)
                rows.append(
                    {
                        "company_name": company.name,
                        "cin": company.cin,
                        "nic_code": company.nic_code,
                        "filing_id": f.id,
                        "financial_year": fy_label(f.financial_year_start, f.financial_year_end),
                        "financial_year_end": f.financial_year_end,
                        "completeness_pct": r.completeness.completeness_pct,
                        "specificity_pct": r.specificity_clarity.specificity_pct,
                        "clarity_pct": r.specificity_clarity.clarity_pct,
                        "sdg_alignment_pct": r.sdg.sdg_alignment_pct,
                        "transparency_score": r.composite_score,
                    }
                )

    if not rows:
        print("No matching companies / filings found.")
        return

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    print(f"Saved {len(rows)} rows -> {out}\n")
    print(f"{'company':45} {'year':10} {'C':>6} {'Sp':>6} {'Cl':>6} {'SDG':>6} {'TS':>6}")
    for r in rows:
        print(
            f"{r['company_name'][:44]:45} {r['financial_year']:10} "
            f"{r['completeness_pct']:6.2f} {r['specificity_pct']:6.2f} "
            f"{r['clarity_pct']:6.2f} {r['sdg_alignment_pct']:6.2f} {r['transparency_score']:6.2f}"
        )


if __name__ == "__main__":
    main()