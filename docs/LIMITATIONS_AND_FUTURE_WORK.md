# Limitations and Future Work

This section documents what the current system deliberately does not
do, and why — distinguishing between things that were out of scope by
design, things that were tried and found not worth pursuing, and things
genuinely deferred due to time constraints.

## 1. Temporal / Year-over-Year Tracking

The current system computes Transparency Scores, greenwashing signals,
and peer-sector benchmarks against each company's most recent BRSR
filing (FY 2025-26), providing a robust point-in-time assessment across
1,164 companies. However, longitudinal tracking — analyzing how a
company's disclosure quality, Transparency Score, and greenwashing risk
evolve across multiple financial years — has not been implemented, and
is identified as a priority direction for future work. This would
require ingesting each company's prior-year BRSR XBRL filings (which
NSE also publishes) into the existing database schema, which already
supports multiple `Filing` records per company via its
`financial_year_start`/`financial_year_end` fields — making this an
extension of the existing ingestion pipeline rather than a redesign.
Once multi-year data is available, planned analyses include
year-over-year Transparency Score trend visualization, statistical
trend-significance testing (e.g. the Mann-Kendall test, appropriate for
the short time series typical of BRSR's mandatory reporting history
since FY 2022-23), and a "silent regression" detector that flags
companies whose disclosure quality or specific metrics have declined
despite an improving or steady overall score.

## 2. PDF/OCR Support

Deliberately not implemented, and not planned. Tested directly in the
project's early phase (see `01_ingestion/README.md`) and found
unreliable (~70-75% row-level accuracy on real BRSR tables, due to
structural issues — merged headers across gender/period sub-categories —
that no general-purpose PDF-table extractor resolves reliably). The
project's core methodological contribution rests on using SEBI's
officially-tagged XBRL data instead, and reintroducing PDF support would
work against that design choice rather than complement it.

## 3. Fine-Grained SDG Target Mapping

The current SDG Alignment component maps disclosures to the 17 top-level
UN SDGs via a principle-to-goal correspondence table. The report's
original plan described mapping to the 169 individual SDG _targets_
(sub-goals) — a finer-grained mapping this project does not attempt, as
it would require expert curation of a 9-principle-to-169-target
correspondence this project has no verified source for. The current
principle-to-17-goal mapping is disclosed as a coarser, achievable
substitute.

## 4. Production Infrastructure (Docker, Kubernetes, Redis/Celery job

queues, JWT authentication with role-based access control)

Not implemented. The original project plan describes these as "Phase 2,
planned" infrastructure — this project's scope prioritized building and
validating the actual analysis pipeline (data ingestion through
Transparency Score) over production deployment hardening, consistent
with the original plan's own phasing.

## 5. XGBoost as the Primary Greenwashing Classifier

Explored directly (see `04_greenwashing_detection/README.md`) rather
than assumed unnecessary. Given the small human-labeled validation
sample available (n=80), and the result that the hand-tuned rule-based
system achieved a higher F1 than XGBoost on the same data (0.732 vs
0.675), the rule-based system was kept as the production component. A
larger labeled dataset (collected via further manual validation rounds)
would be needed to properly assess whether a learned classifier could
outperform the hand-tuned rules at scale — this is a natural next step
if greenwashing-detection accuracy needs to improve further.

## 6. Independent Expert Human Validation

The project's human-validation study (Transparency Score correlation,
n=20; greenwashing detector validation, n=80 total) was conducted with
LLM-assisted scoring rather than an independent panel of trained ESG
analysts — disclosed explicitly throughout rather than presented as
equivalent to expert validation. A genuinely independent expert-analyst
study, ideally with multiple raters and measured inter-rater agreement
(e.g. Cohen's Kappa, as originally planned for the BERT classifier's
training labels), would strengthen these validation results
considerably and is a natural extension if institutional access to
domain experts becomes available.
