"""
Runs the complete Transparency Score pipeline across every ingested
company's latest filing, and writes a summary CSV + prints distribution
statistics — the dataset-level result needed for the paper (score
distribution, top/bottom performers, per-component breakdowns).

This is a read-only analysis pass — no data is modified. Safe to re-run
at any time as more companies are ingested.
"""
import csv
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from analysis.completeness_score import get_concept_universe
from analysis.queries import get_latest_filing
from analysis.transparency_score import get_transparency_score
from db.models import Company
from db.session import get_session, init_db

OUTPUT_PATH = Path("data/analysis/transparency_scores.csv")


def progress_bar(done: int, total: int, width: int = 30) -> str:
    filled = int(width * done / total) if total else 0
    pct = (done / total * 100) if total else 0.0
    return f"[{'█' * filled}{'░' * (width - filled)}] {pct:5.1f}% ({done}/{total})"


def main():
    init_db()
    with get_session() as session:
        companies = session.query(Company).all()
        total = len(companies)
        print(f"Computing Transparency Scores for {total} companies...")
        print("Building shared concept-universe (one-time cost)...")
        concept_universe = get_concept_universe(session)
        print(f"Concept universe size: {len(concept_universe)}\n")

        results = []
        errors = []
        start_time = time.time()

        for i, company in enumerate(companies, start=1):
            if i % 10 == 0 or i == total:
                elapsed = time.time() - start_time
                print(f"{progress_bar(i, total)}  ({elapsed:.0f}s elapsed)")

            filing = get_latest_filing(session, company.id)
            if filing is None:
                continue

            try:
                result = get_transparency_score(session, filing.id, concept_universe=concept_universe)
                results.append({
                    "company_name": company.name,
                    "cin": company.cin,
                    "completeness_pct": result.completeness.completeness_pct,
                    "specificity_pct": result.specificity_clarity.specificity_pct,
                    "clarity_pct": result.specificity_clarity.clarity_pct,
                    "sdg_alignment_pct": result.sdg.sdg_alignment_pct,
                    "transparency_score": result.composite_score,
                    "total_narrative_segments": result.specificity_clarity.total_segments,
                })
            except Exception as e:
                errors.append((company.name, f"{type(e).__name__}: {e}"))

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "company_name", "cin", "completeness_pct", "specificity_pct",
            "clarity_pct", "sdg_alignment_pct", "transparency_score", "total_narrative_segments",
        ])
        writer.writeheader()
        writer.writerows(results)

    print(f"\nWritten {len(results)} scores to {OUTPUT_PATH}")
    if errors:
        print(f"\n{len(errors)} companies failed to score:")
        for name, err in errors[:10]:
            print(f"  {name}: {err}")

    if results:
        scores = sorted(results, key=lambda r: r["transparency_score"])
        n = len(scores)
        print(f"\n=== Distribution (n={n}) ===")
        print(f"Min: {scores[0]['transparency_score']}  ({scores[0]['company_name']})")
        print(f"Max: {scores[-1]['transparency_score']}  ({scores[-1]['company_name']})")
        print(f"Median: {scores[n // 2]['transparency_score']}")
        mean = sum(r["transparency_score"] for r in scores) / n
        print(f"Mean: {round(mean, 2)}")

        print(f"\n=== Bottom 5 ===")
        for r in scores[:5]:
            print(f"  {r['transparency_score']:6.2f}  {r['company_name']}")

        print(f"\n=== Top 5 ===")
        for r in scores[-5:]:
            print(f"  {r['transparency_score']:6.2f}  {r['company_name']}")


if __name__ == "__main__":
    main()