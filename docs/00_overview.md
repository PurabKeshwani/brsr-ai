The corresponding code lives in `scripts/01_ingestion/` through
`scripts/07_reporting/` (numbered to match), with the core reusable
logic in `src/analysis/`, `src/ingestion/`, `src/api/`, and `src/db/`.

## The single biggest architectural decision

Almost every downstream design choice in this project traces back to one
early pivot: **rejecting PDF/OCR extraction in favor of SEBI's official
XBRL filings**, after direct testing showed PDF-table extraction
achieving only ~70-75% row-level accuracy on real BRSR filings (see
`01_ingestion/README.md`). This is a significant departure from how most
comparable academic work in this space approaches BRSR analysis (PDF +
NLP extraction), and it reframes the core technical problem from
"document understanding" to "structured record-linkage" — reading data
that was never structurally lost, instead of trying to reconstruct
structure a PDF renderer had visually merged.

This decision has one honest cost worth stating plainly: because XBRL's
`PrincipleAxis` tagging replaces manual expert annotation as the source
of training labels (see `02_data_exploration/README.md`), this project's
BERT classifier is trained on weak supervision (4,854 samples) rather
than the 12,340 expert-annotated segments described in earlier planning
documents — and its measured F1 (0.6584) is correspondingly lower than
an earlier unverified target (0.82). This is disclosed throughout rather
than hidden, and is treated as a genuine, defensible trade-off: real,
reproducible, lower numbers over unverifiable higher ones.

## What this project actually validated (all real, evidence-backed numbers)

| Component                               | Metric                             | Result                               |
| --------------------------------------- | ---------------------------------- | ------------------------------------ |
| BERT 9-Principle Classifier             | Macro F1 (held-out test)           | 0.6584                               |
| — vs. vanilla (non-domain-adapted) BERT | Macro F1                           | 0.6186                               |
| Greenwashing Detector (hybrid)          | Precision / Recall / F1 / AUC-ROC  | 0.917 / 0.846 / 0.880 / 0.894 (n=30) |
| — XGBoost meta-classifier comparison    | F1 / AUC-ROC                       | 0.675 / 0.764 (n=80, LOOCV)          |
| Compliance Mapper                       | Top-1 accuracy vs. random baseline | 44.3% vs. 11.1% (n=393)              |
| Transparency Score                      | Human-validation Pearson r         | 0.6314 (p=0.0028, n=20)              |
| Companies fully ingested and scored     | —                                  | 1,164 / 1,276                        |

## Components beyond the original project plan

Three analysis modules were built that are not described in the
original planning report or diagrams, identified as valuable additions
given the strength of the XBRL data source:

- **Internal Consistency Checker** (`src/analysis/consistency.py`) —
  auto-discovers gender-split disclosures and verifies filed totals sum
  correctly, catching real filing errors (e.g. Tata Steel's own filing
  showing union-membership percentages that don't sum correctly).
- **Assurance Coverage Analyzer** (`src/analysis/assurance.py`) —
  measures what fraction of a company's disclosures are backed by
  third-party assurance, and at what confidence level (Reasonable vs.
  Limited).
- **Silent Removal Detector** (`src/analysis/silent_removal.py`) —
  flags metrics disclosed in a company's own prior-year context that are
  absent from the current year, a failure mode no claim-vs-claim
  contradiction check can catch, since there's no statement to compare
  against when something has simply disappeared.

These three, together with the claim-vs-XBRL-number contradiction
detector, are unified under a single **Truth Auditor** module
(`src/analysis/truth_auditor.py`) — the project's answer to what the
original plan called an "MNLI-based contradiction detector," implemented
instead as evidence-based verification against the company's own filed
regulatory data (see `04_greenwashing_detection/README.md` for the full
reasoning on why this is a stronger form of evidence).

## How to read the bug-fix logs

Every phase document includes a "Real bugs found and fixed here" section
with the actual diagnostic evidence — not just "we fixed a bug," but the
specific symptom observed, the hypothesis tested, the evidence that
confirmed or ruled out that hypothesis, and the final fix. This is
deliberate: across the project, several bugs recurred as the _same
underlying pattern_ appearing in different modules (e.g. cross-principle
boilerplate text distorting results in Phase 2, Phase 3, and Phase 5
independently), and tracing that pattern honestly across phases is
itself part of the project's technical narrative — not something to
smooth over into a single generic "we did rigorous testing" statement.

## structure

docs/
├── 00_overview.md <- you are here
├── 01_ingestion/ <- XBRL data pipeline
├── 02_data_exploration/ <- weak-supervision label verification
├── 03_bert_training/ <- domain-adaptive pretraining + classifier
├── 04_greenwashing_detection/ <- hybrid lexicon+semantic+XGBoost
├── 05_compliance_mapper/ <- NGRBC-alignment scoring
├── 06_transparency_score/ <- composite score + peer benchmarking
├── 07_reporting/ <- API layer + final aggregation
└── LIMITATIONS_AND_FUTURE_WORK.md

The corresponding code lives in `scripts/01_ingestion/` through
`scripts/07_reporting/` (numbered to match), with the core reusable
logic in `src/analysis/`, `src/ingestion/`, `src/api/`, and `src/db/`.

## The single biggest architectural decision

Almost every downstream design choice in this project traces back to one
early pivot: **rejecting PDF/OCR extraction in favor of SEBI's official
XBRL filings**, after direct testing showed PDF-table extraction
achieving only ~70-75% row-level accuracy on real BRSR filings (see
`01_ingestion/README.md`). This is a significant departure from how most
comparable academic work in this space approaches BRSR analysis (PDF +
NLP extraction), and it reframes the core technical problem from
"document understanding" to "structured record-linkage" — reading data
that was never structurally lost, instead of trying to reconstruct
structure a PDF renderer had visually merged.

This decision has one honest cost worth stating plainly: because XBRL's
`PrincipleAxis` tagging replaces manual expert annotation as the source
of training labels (see `02_data_exploration/README.md`), this project's
BERT classifier is trained on weak supervision (4,854 samples) rather
than the 12,340 expert-annotated segments described in earlier planning
documents — and its measured F1 (0.6584) is correspondingly lower than
an earlier unverified target (0.82). This is disclosed throughout rather
than hidden, and is treated as a genuine, defensible trade-off: real,
reproducible, lower numbers over unverifiable higher ones.

## What this project actually validated (all real, evidence-backed numbers)

| Component                               | Metric                             | Result                               |
| --------------------------------------- | ---------------------------------- | ------------------------------------ |
| BERT 9-Principle Classifier             | Macro F1 (held-out test)           | 0.6584                               |
| — vs. vanilla (non-domain-adapted) BERT | Macro F1                           | 0.6186                               |
| Greenwashing Detector (hybrid)          | Precision / Recall / F1 / AUC-ROC  | 0.917 / 0.846 / 0.880 / 0.894 (n=30) |
| — XGBoost meta-classifier comparison    | F1 / AUC-ROC                       | 0.675 / 0.764 (n=80, LOOCV)          |
| Compliance Mapper                       | Top-1 accuracy vs. random baseline | 44.3% vs. 11.1% (n=393)              |
| Transparency Score                      | Human-validation Pearson r         | 0.6314 (p=0.0028, n=20)              |
| Companies fully ingested and scored     | —                                  | 1,164 / 1,276                        |

## Components beyond the original project plan

Three analysis modules were built that are not described in the
original planning report or diagrams, identified as valuable additions
given the strength of the XBRL data source:

- **Internal Consistency Checker** (`src/analysis/consistency.py`) —
  auto-discovers gender-split disclosures and verifies filed totals sum
  correctly, catching real filing errors (e.g. Tata Steel's own filing
  showing union-membership percentages that don't sum correctly).
- **Assurance Coverage Analyzer** (`src/analysis/assurance.py`) —
  measures what fraction of a company's disclosures are backed by
  third-party assurance, and at what confidence level (Reasonable vs.
  Limited).
- **Silent Removal Detector** (`src/analysis/silent_removal.py`) —
  flags metrics disclosed in a company's own prior-year context that are
  absent from the current year, a failure mode no claim-vs-claim
  contradiction check can catch, since there's no statement to compare
  against when something has simply disappeared.

These three, together with the claim-vs-XBRL-number contradiction
detector, are unified under a single **Truth Auditor** module
(`src/analysis/truth_auditor.py`) — the project's answer to what the
original plan called an "MNLI-based contradiction detector," implemented
instead as evidence-based verification against the company's own filed
regulatory data (see `04_greenwashing_detection/README.md` for the full
reasoning on why this is a stronger form of evidence).

## How to read the bug-fix logs

Every phase document includes a "Real bugs found and fixed here" section
with the actual diagnostic evidence — not just "we fixed a bug," but the
specific symptom observed, the hypothesis tested, the evidence that
confirmed or ruled out that hypothesis, and the final fix. This is
deliberate: across the project, several bugs recurred as the _same
underlying pattern_ appearing in different modules (e.g. cross-principle
boilerplate text distorting results in Phase 2, Phase 3, and Phase 5
independently), and tracing that pattern honestly across phases is
itself part of the project's technical narrative — not something to
smooth over into a single generic "we did rigorous testing" statement.
