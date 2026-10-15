\# Phase 1: Data Ingestion (XBRL Pipeline)



\## What this phase does



This phase takes SEBI's officially-tagged BRSR XBRL filings (published

alongside PDF filings on NSE) and converts them into structured database

records. The pipeline downloads each company's XBRL file, parses it into

individual "facts" (a fact = one tagged value, e.g. `TotalScope1Emissions

= "870.29"` with a dimensional context like gender or reporting period),

and stores them in a relational database (`Company`, `Filing`, `Fact`

tables).



Core files:

\- `src/ingestion/xbrl\_parser.py` — parses raw XBRL XML into `XbrlFact`

&#x20; objects (concept name, value, unit, decimals, dimensional context)

\- `src/ingestion/xbrl\_ingest.py` — orchestrates download, parsing, and

&#x20; database storage; handles re-ingestion (idempotency) and error cases

\- `scripts/01\_ingestion/ingest\_company.py` — CLI for ingesting a single

&#x20; company

\- `scripts/01\_ingestion/bulk\_ingest.py` — resumable bulk ingestion across

&#x20; the full NSE filings CSV (1,276 companies)

\- `scripts/01\_ingestion/populate\_nic\_codes.py` — extracts each company's

&#x20; NIC (industry classification) code for later sector benchmarking



\## Why this approach (not alternatives)



\*\*The original plan was PDF extraction\*\* (PDFPlumber for digital text +

Tesseract OCR for scanned documents), matching how most academic ESG-NLP

papers approach BRSR analysis. This was tested directly: a sample BRSR

PDF (Glenmark Pharmaceuticals) was run through both a native

PDFPlumber-based extractor and a hybrid Docling-VLM (vision-language

model) extractor, and both were checked against the actual filed values.



\*\*Result: neither approach reliably extracted BRSR's tables.\*\* The core

problem is structural, not a tooling limitation — BRSR PDF tables

routinely merge headers across multiple sub-categories (e.g. a single

header cell spanning "Male", "Female", "Other" columns, or spanning

current-year/previous-year periods), and this merged-header structure is

not something any general-purpose PDF-table extractor parses reliably.

Row-level accuracy in testing came out around 70-75% — meaning roughly

1 in 4 extracted values could be silently wrong, with no way to detect

which ones without manual cross-checking against the source PDF.



\*\*The XBRL discovery changed the entire project's direction.\*\* While

investigating BRSR's data structure, it became clear that NSE publishes

XBRL (eXtensible Business Reporting Language) alongside every BRSR PDF —

a machine-readable, officially SEBI-tagged version of the exact same

data, where every value already has an explicit concept name and

dimensional context (no merged-header ambiguity, because the tagging is

done by the filer against a fixed taxonomy, not inferred from visual

table layout).



This is why the project pivoted from "PDF text/table extraction problem"

to "structured record-linkage problem" — instead of trying to

\*reconstruct\* structure that a PDF renderer had visually merged, the

system reads structure that was never lost in the first place.



\## Key decisions and trade-offs



\*\*Decision: never alter values at extraction time.\*\* `XbrlFact.value` is

always stored as the raw string exactly as filed — type conversion

(`to\_number()`) only happens at the analysis layer, not during ingestion.

This means a malformed or unusual value doesn't get silently coerced or

dropped during ingestion; it gets stored as-is and any downstream

component that can't parse it fails loudly rather than substituting a

default.



\*\*Decision: never silently drop ingestion failures.\*\* Every failure mode

(malformed XML, missing CIN, missing financial year, network error,

suspiciously small downloaded file) raises an explicit `IngestionError`

rather than being caught and skipped. For bulk runs, failures are logged

to a `bulk\_ingest\_progress.csv` file with the exact reason, so a failed

company is never silently missing from the dataset without a record of

why.



\*\*Decision: idempotent re-ingestion via delete-then-insert.\*\* If the same

company/financial-year combination is ingested twice (e.g. the file was

corrected, or the pipeline was re-run), the old `Filing` and its `Fact`

rows are deleted and replaced — not appended alongside. This was

specifically tested (see Bug Fixes Log) because an early version of the

bulk pipeline had a resumability bug that caused companies to be

re-ingested multiple times; idempotency at the database layer meant this

inefficiency never corrupted the actual stored data, even though it

wasted processing time.



\*\*Trade-off accepted: single-financial-year scope.\*\* The current pipeline

ingests each company's \*latest\* filing only, not historical years. This

was a deliberate scope decision to prioritize breadth (more companies)

over depth (multi-year history per company) within the project's

timeline — documented as a "Future Work" item (temporal/year-over-year

tracking) rather than left unaddressed.



\## Real bugs found and fixed here



1\. \*\*CSV parsing failures (delimiter/encoding mismatch).\*\* The NSE

&#x20;  filings CSV turned out to be comma-delimited with a UTF-8 BOM and

&#x20;  embedded newlines inside quoted header cells (e.g. the raw header

&#x20;  text was literally `"COMPANY \\n"`) — not the tab-delimited format

&#x20;  initially assumed. Diagnosed by inspecting the raw file bytes directly

&#x20;  (`repr()` of the first 500 bytes) rather than guessing at the format,

&#x20;  which immediately showed the actual delimiter and BOM.



2\. \*\*Bulk resumability bug — the "skip already-successful companies"

&#x20;  check was silently missing.\*\* During a CSV-parsing rewrite, the

&#x20;  filtering logic that checked a company's prior status against the

&#x20;  progress log was accidentally dropped from the loop, even though the

&#x20;  log was still being loaded and printed. This meant every bulk run

&#x20;  re-attempted every company in the CSV from the top, regardless of

&#x20;  `--limit`, wasting significant time re-downloading and re-parsing

&#x20;  already-ingested companies. Confirmed by writing a small diagnostic

&#x20;  script that directly compared a company's logged status against

&#x20;  what the loop was actually doing — found the missing `continue`

&#x20;  check by reading the live file content rather than assuming the

&#x20;  fix from a prior edit had been applied.



3\. \*\*Malformed XML crashed with a raw exception instead of a clean

&#x20;  error.\*\* `ingest\_filing()` originally called `parse\_xbrl()` without a

&#x20;  try/except around XML parsing, so a truncated or corrupted download

&#x20;  would raise a raw `xml.etree.ElementTree.ParseError` instead of the

&#x20;  module's own `IngestionError`. This was caught by a synthetic test

&#x20;  (a deliberately malformed XML fixture), not by observing it in

&#x20;  production — testing the failure path directly, rather than waiting

&#x20;  to encounter it accidentally.



4\. \*\*A genuinely corrupted download (Shilpa Medicare Limited).\*\* One

&#x20;  company's XBRL file failed to parse with an "unclosed token" error.

&#x20;  Investigation confirmed the downloaded file was truly truncated

&#x20;  mid-download (the last line was cut off before the closing

&#x20;  `</xbrli:xbrl>` tag) — a real network/download issue, not a bug in the

&#x20;  parsing code. This was distinguished from a code bug by checking the

&#x20;  file's line count and comparing the reported error location against

&#x20;  the actual file length.



\## Your personal reflection (fill this in yourself)



\*\[This section is intentionally left for you to write in your own words.

Some starting questions to reflect on, based on the actual decisions

above:]\*



\- When the PDF-extraction tests came back at \~70-75% accuracy, what was

&#x20; your reaction? Did you push for continuing to improve PDF extraction,

&#x20; or did the XBRL discovery feel like an obvious pivot once you saw it?

\- Looking at the "never silently drop failures" decision — do you agree

&#x20; with always raising loud errors even for something like one corrupted

&#x20; download, versus quietly skipping and moving on? What would you have

&#x20; chosen, and why?

\- The resumability bug wasted real processing time across multiple bulk

&#x20; runs before it was caught. What would you personally check first, next

&#x20; time, to catch a bug like this earlier?

