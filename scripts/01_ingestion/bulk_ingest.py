"""
Bulk XBRL ingestion — reads the NSE filings CSV and ingests each company's
BRSR XBRL into the database via the existing single-company pipeline
(ingestion.xbrl_ingest.ingest_company_by_url), which is already idempotent
and error-safe (see tests/test_xbrl_ingest.py).

Resumable by design: before attempting each company, checks whether it's
already ingested (by CIN, once we know it — but since we only know the
company NAME from the CSV before ingesting, we track progress by a
separate "already attempted" log keyed on company name, so re-running
after an interruption skips companies already successfully ingested OR
already recorded as a permanent failure, without re-hitting NSE for them).

Usage:
    python scripts/bulk_ingest.py data/filings.csv --limit 80
    python scripts/bulk_ingest.py data/filings.csv --limit 80 --retry-failures
"""
from __future__ import annotations

import argparse
import csv
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from db.session import get_session, init_db  # noqa: E402
from ingestion.xbrl_ingest import IngestionError, ingest_company_by_url  # noqa: E402

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

PROGRESS_LOG = Path("data/bulk_ingest_progress.csv")  # company_name, status, detail
REQUEST_DELAY_SECONDS = 1.5  # polite spacing between NSE requests


def find_column(header: list[str], *keywords: str) -> str:
    for col in header:
        normalized = col.lower().replace("\n", " ").strip()
        if all(kw in normalized for kw in keywords):
            return col
    raise KeyError(f"No column matching {keywords} in: {header}")


def load_already_attempted() -> dict[str, str]:
    """Returns {company_name: status} from a prior run, if any."""
    if not PROGRESS_LOG.exists():
        return {}
    with open(PROGRESS_LOG, newline="", encoding="utf-8") as f:
        return {row["company_name"]: row["status"] for row in csv.DictReader(f)}


def append_progress(company_name: str, status: str, detail: str) -> None:
    PROGRESS_LOG.parent.mkdir(parents=True, exist_ok=True)
    is_new = not PROGRESS_LOG.exists()
    with open(PROGRESS_LOG, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow(["company_name", "status", "detail"])
        writer.writerow([company_name, status, detail])


def progress_bar(done: int, total: int, width: int = 30) -> str:
    filled = int(width * done / total) if total else 0
    pct = (done / total * 100) if total else 0.0
    return f"[{'█' * filled}{'░' * (width - filled)}] {pct:5.1f}% ({done}/{total})"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv_path")
    ap.add_argument("--limit", type=int, default=80, help="max NEW companies to attempt this run")
    ap.add_argument("--retry-failures", action="store_true", help="also retry companies previously marked failed")
    args = ap.parse_args()

    init_db()

    # Real CSV inspected: tab-delimited (not comma), UTF-8 BOM at file start,
    # and header cells contain stray quotes/asterisks/newlines (e.g.
    # '"**XBRL \n"'). encoding="utf-8-sig" strips the BOM; delimiter="\t"
    # matches the actual format; find_column already normalizes whitespace,
    # but header values also need quote/asterisk stripping before matching.
    # Real file format confirmed by inspecting raw bytes: UTF-8 with BOM,
    # COMMA-delimited (not tab), with each field individually quoted and
    # header cells containing a literal embedded newline before the
    # closing quote (e.g. the raw header cell is '"COMPANY \n"'). Python's
    # csv module handles quoted embedded newlines correctly on its own
    # when the file is opened with newline="" — no special handling
    # needed beyond using the correct delimiter and encoding.
    with open(args.csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=",")
        original_fieldnames = reader.fieldnames
        header = [h.strip().strip("*").strip() for h in original_fieldnames]
        company_col_clean = find_column(header, "company")
        xbrl_col_clean = find_column(header, "xbrl")

        original_by_clean = {
            h.strip().strip("*").strip(): h for h in original_fieldnames
        }
        company_col = original_by_clean[company_col_clean]
        xbrl_col = original_by_clean[xbrl_col_clean]

        rows = list(reader)

    print(f"Detected columns — company: {company_col!r}, xbrl: {xbrl_col!r}\n")

    already = load_already_attempted()
    print(f"Found {len(rows)} rows in CSV. {len(already)} previously attempted "
          f"({sum(1 for s in already.values() if s == 'success')} succeeded, "
          f"{sum(1 for s in already.values() if s == 'failed')} failed).")

    to_attempt = []
    for row in rows:
        name = row[company_col].strip()
        url = row[xbrl_col].strip()
        if not name or not url or url.lower() in {"nan", "-", ""}:
            continue

        prior_status = already.get(name)
        if prior_status == "success":
            continue
        if prior_status == "failed" and not args.retry_failures:
            continue

        to_attempt.append((name, url))

    to_attempt = to_attempt[: args.limit]
    total = len(to_attempt)
    print(f"Attempting {total} new companies this run (limit={args.limit}).\n")

    succeeded, failed = 0, 0
    for i, (name, url) in enumerate(to_attempt, start=1):
        print(f"{progress_bar(i - 1, total)}  {name[:50]}")
        try:
            with get_session() as session:
                filing = ingest_company_by_url(session, url, name)
                print(f"    OK — {filing.raw_fact_count:,} facts")
                append_progress(name, "success", f"filing_id={filing.id}, facts={filing.raw_fact_count}")
                succeeded += 1
        except IngestionError as e:
            print(f"    FAILED — {e}")
            append_progress(name, "failed", str(e))
            failed += 1
        except Exception as e:
            # Deliberately caught broadly here (unlike the single-company
            # script) because a bulk run must not die on one bad row —
            # but the exception type/message is always logged, never
            # silently swallowed.
            print(f"    UNEXPECTED ERROR — {type(e).__name__}: {e}")
            append_progress(name, "failed", f"{type(e).__name__}: {e}")
            failed += 1

        time.sleep(REQUEST_DELAY_SECONDS)

    print(f"\n{progress_bar(total, total)}  done")
    print(f"This run: {succeeded} succeeded, {failed} failed")
    print(f"Progress log: {PROGRESS_LOG}")


if __name__ == "__main__":
    main()
