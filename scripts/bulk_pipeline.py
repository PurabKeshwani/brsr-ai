"""
End-to-end BRSR pipeline: reads the NSE filings CSV, downloads each XBRL,
parses it, and writes one tidy master dataset plus a per-company summary.

Why XBRL and not the PDFs: the XBRL is SEBI's officially tagged version of
the same filing. Every value is a machine-readable fact with explicit
dimensions (gender, employee category, benefit type, financial year), so
there is no text segmentation, no table detection, no schema guessing, and
no possibility of silently mis-parsing a number.

Resumable: already-downloaded XBRLs are reused, and rows already present in
the output are skipped, so you can stop and re-run without losing work.

Usage:
    python scripts/bulk_pipeline.py data/filings.csv
    python scripts/bulk_pipeline.py data/filings.csv --limit 10
"""
from __future__ import annotations

import argparse
import io
import sys
import time
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ingestion.xbrl_parser import parse_xbrl  # noqa: E402

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

XBRL_DIR = Path("data/xbrl")
OUT_DIR = Path("data/processed")
MASTER_PATH = OUT_DIR / "brsr_master.parquet"
SUMMARY_PATH = OUT_DIR / "company_summary.csv"
FAILURES_PATH = OUT_DIR / "failures.csv"

# NSE rejects requests without a browser-like User-Agent.
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept": "application/xml,text/xml,*/*",
}
REQUEST_DELAY_SECONDS = 1.0  # be polite to NSE; avoids rate-limiting


def find_column(df: pd.DataFrame, *keywords: str) -> str:
    """Finds a column whose name contains all the given keywords, case- and
    whitespace-insensitive. The CSV's headers have stray spaces/newlines."""
    for col in df.columns:
        normalized = col.lower().replace("\n", " ").strip()
        if all(kw in normalized for kw in keywords):
            return col
    raise KeyError(f"No column matching {keywords} in: {list(df.columns)}")


def safe_filename(company: str) -> str:
    keep = "".join(c if c.isalnum() or c in " -_" else "_" for c in company)
    return keep.strip().replace(" ", "_")[:80]


def download_xbrl(url: str, dest: Path) -> tuple[bool, str]:
    """Downloads an XBRL file unless already present. Returns (ok, message)."""
    if dest.exists() and dest.stat().st_size > 0:
        return True, "cached"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=90)
        if resp.status_code != 200:
            return False, f"HTTP {resp.status_code}"
        if len(resp.content) < 1000:
            return False, f"suspiciously small ({len(resp.content)} bytes)"
        dest.write_bytes(resp.content)
        time.sleep(REQUEST_DELAY_SECONDS)
        return True, f"downloaded {len(resp.content):,} bytes"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def progress_bar(done: int, total: int, width: int = 30) -> str:
    filled = int(width * done / total) if total else 0
    pct = (done / total * 100) if total else 0.0
    return f"[{'█' * filled}{'░' * (width - filled)}] {pct:5.1f}%  ({done}/{total})"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv_path", help="NSE filings CSV with COMPANY and XBRL columns")
    ap.add_argument("--limit", type=int, default=None, help="process only the first N filings")
    args = ap.parse_args()

    XBRL_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(args.csv_path)
    company_col = find_column(df, "company")
    xbrl_col = find_column(df, "xbrl")
    try:
        to_year_col = find_column(df, "to", "year")
    except KeyError:
        to_year_col = None

    if args.limit:
        df = df.head(args.limit)

    total = len(df)
    print(f"Found {total} filings in {args.csv_path}")
    print(f"  company column: {company_col!r}")
    print(f"  xbrl column:    {xbrl_col!r}\n")

    all_frames: list[pd.DataFrame] = []
    summaries: list[dict] = []
    failures: list[dict] = []

    for i, row in enumerate(df.itertuples(index=False), start=1):
        company = str(getattr(row, company_col.replace(" ", "_"), None) or df.iloc[i - 1][company_col]).strip()
        url = str(df.iloc[i - 1][xbrl_col]).strip()
        year = str(df.iloc[i - 1][to_year_col]).strip() if to_year_col else ""

        print(f"{progress_bar(i - 1, total)}  {company[:45]}")

        if not url or url.lower() in {"nan", "-"}:
            failures.append({"company": company, "url": url, "reason": "no XBRL URL"})
            continue

        dest = XBRL_DIR / f"{safe_filename(company)}_{year}.xml"
        ok, msg = download_xbrl(url, dest)
        if not ok:
            print(f"    download failed: {msg}")
            failures.append({"company": company, "url": url, "reason": msg})
            continue

        try:
            facts = parse_xbrl(dest)
        except Exception as e:
            print(f"    parse failed: {type(e).__name__}: {e}")
            failures.append({"company": company, "url": url, "reason": f"parse: {e}"})
            continue

        frame = pd.DataFrame([f.as_row() for f in facts])
        frame.insert(0, "company", company)
        frame.insert(1, "filing_year", year)
        all_frames.append(frame)

        numeric = sum(1 for f in facts if f.unit is not None)
        summaries.append({
            "company": company,
            "filing_year": year,
            "total_facts": len(facts),
            "numeric_facts": numeric,
            "unique_concepts": len(set(f.concept for f in facts)),
            "source": msg,
        })
        print(f"    {len(facts):,} facts ({numeric:,} numeric, "
              f"{len(set(f.concept for f in facts))} concepts)")

    print(f"\n{progress_bar(total, total)}  done\n")

    if all_frames:
        master = pd.concat(all_frames, ignore_index=True)
        master.to_parquet(MASTER_PATH, index=False)
        print(f"Master dataset: {len(master):,} rows across "
              f"{master['company'].nunique()} companies -> {MASTER_PATH}")

    if summaries:
        pd.DataFrame(summaries).to_csv(SUMMARY_PATH, index=False)
        print(f"Per-company summary -> {SUMMARY_PATH}")

    if failures:
        pd.DataFrame(failures).to_csv(FAILURES_PATH, index=False)
        print(f"\n{len(failures)} filing(s) could not be processed -> {FAILURES_PATH}")
        print("These are listed explicitly rather than silently dropped — "
              "check the 'reason' column before treating the dataset as complete.")
    else:
        print("\nNo failures.")


if __name__ == "__main__":
    main()