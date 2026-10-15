"""
Diagnostic — compares how a company name appears in the progress log
(data/bulk_ingest_progress.csv) versus how it's parsed fresh from the
source CSV (data/filings.csv), to find why the "skip already-successful
companies" resume logic in bulk_ingest.py never actually skips anything.
"""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from bulk_ingest import find_column  # reuse the exact same column-detection logic


def main():
    with open("data/bulk_ingest_progress.csv", encoding="utf-8") as f:
        log_rows = list(csv.DictReader(f))

    niit_in_log = next((r for r in log_rows if "NIIT Learning" in r["company_name"]), None)
    print("Name in progress log:", repr(niit_in_log["company_name"]) if niit_in_log else "NOT FOUND")
    print("Status in progress log:", niit_in_log["status"] if niit_in_log else "N/A")

    with open("data/filings.csv", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=",")
        original_fieldnames = reader.fieldnames
        header = [h.strip().strip("*").strip() for h in original_fieldnames]
        company_col_clean = find_column(header, "company")
        original_by_clean = {h.strip().strip("*").strip(): h for h in original_fieldnames}
        company_col = original_by_clean[company_col_clean]

        print(f"\nDetected company column name: {company_col!r}")

        for row in reader:
            name = row[company_col].strip()
            if "NIIT Learning" in name:
                print("Name freshly parsed from CSV:", repr(name))
                print("\nAre they equal?", name == niit_in_log["company_name"])
                break


if __name__ == "__main__":
    main()
