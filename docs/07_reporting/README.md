# Phase 7: Reporting Layer & Final Aggregation

## What this phase does

This is the thinnest phase in the project, by design — it doesn't
introduce new analysis logic. It aggregates outputs from every prior
phase into a single, readable per-company summary, matching what the
production API and frontend ultimately display.

Core files:

- `scripts/07_reporting/run_full_analysis.py` — a CLI script that runs
  the complete analysis suite (trends, consistency, assurance,
  greenwashing signals, silent removal) against one company and prints a
  full readable report — the same cross-company validation harness used
  throughout the project (see Phase 1-6 bug logs) to confirm each new
  module generalized correctly beyond the company it was originally
  built and tested against
- `src/api/routes.py`, `schemas.py`, `converters.py` — the FastAPI
  backend that exposes every analysis component (Transparency Score,
  Truth Auditor, Sector Benchmark, Trends, Consistency, Assurance,
  Greenwashing Signals) as typed REST endpoints, plus a live
  upload-and-analyze endpoint and a peer-comparison endpoint

## Why this approach (not alternatives)

**Deliberately no new logic at this layer.** Every number the API
returns is computed by reusing the exact same functions already built
and validated in Phases 1-6 — the API layer's only job is translation
(internal dataclasses → typed Pydantic response models) and orchestration
(calling the right sequence of already-tested functions per request).
This was a deliberate design boundary: if a bug appeared in a report
output, it should be traceable to one specific, already-documented
analysis module, not to duplicated logic living separately in the API
layer.

**Why `run_full_analysis.py` existed before the API did.** This script
was the project's own cross-company validation tool throughout
development — every time a new analysis module was built (e.g. the
Compliance Mapper, the Transparency Score), it was run against multiple
different companies via this script specifically to catch bugs that only
appear on companies the module wasn't originally designed against (this
is how several real bugs in Phases 4-6 were first noticed — a company's
output looking wrong or suspiciously uniform when this script was run
against it).

**Why the live upload-and-analyze endpoint reuses `ingest_filing()`
directly, not a separate upload-specific pipeline.** A user-submitted
XBRL file is ingested through the exact same function used for the bulk
pipeline (`src/ingestion/xbrl_ingest.py`), so any bug fix or validation
already built into the core ingestion pipeline (malformed-XML handling,
idempotent re-ingestion, missing-field errors) automatically applies to
live uploads too, without needing to be separately re-implemented or
re-tested.

## Key decisions and trade-offs

**Decision: the upload endpoint explicitly only accepts `.xml`/`.xbrl`
files, rejecting other formats (including PDF) with a clear explanation
in the error message.** This mirrors the project's foundational Phase 1
decision (PDF/OCR extraction was tested and found unreliable, ~70-75%
accuracy) — rather than silently ignoring the possibility of PDF
support, the API's rejection message states the reasoning directly, so
a user attempting to upload a PDF understands _why_ it's not supported,
not just that it failed.

**Trade-off accepted: peer comparison is capped at 5 companies per
request**, a practical limit chosen to keep response times and frontend
layout manageable, not derived from any deeper analytical constraint.

## Real bugs found and fixed here

1. **File-upload support required an undeclared dependency
   (`python-multipart`).** FastAPI's `UploadFile` handling silently
   requires this package to parse multipart form data, and its absence
   only surfaced as a runtime `RuntimeError` at server startup once the
   upload route was added — not caught until the server was actually
   restarted after adding the endpoint. Fixed with a one-line dependency
   install; kept here as a reminder that a route can be written
   correctly and still fail purely due to a missing transitive
   dependency.

## Your personal reflection (fill this in yourself)

_[This section is intentionally left for you to write in your own words.
Some starting questions to reflect on, based on the actual decisions
above:]_

- The API layer deliberately contains no new analysis logic of its own.
  Why do you think that boundary matters for a project like this, where
  multiple different modules (BERT, greenwashing detection, transparency
  scoring) all needed to be exposed together?
- `run_full_analysis.py` was used throughout the project as an informal
  testing tool before it became a "reporting" script. Do you think
  reusing a debugging tool as a production feature like this is good
  practice, or would you have built a separate, dedicated reporting
  script from scratch? Why?
