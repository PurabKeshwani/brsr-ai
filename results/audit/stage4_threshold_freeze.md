# Stage 4 Detector Freeze

**Freeze date:** 2026-10-18  
**Detector under this freeze:** fixed rule-based **text vagueness subdetector**, combining the lexicon and semantic signals. The integrated auditor also exposes claim-vs-figure and assurance-gap checks, but the available text-only human labels do not evaluate those database-context signals. The XGBoost meta-classifier is experimental and is not the evaluated final engine.

The current vagueness subdetector implementation is frozen before recomputing development-set metrics and before Batch 3 is labeled. Do not tune its rules or thresholds after evaluating these samples. The development evaluation script writes SHA-256 fingerprints for the three subdetector source files to `data/validation/stage4_detector_freeze.json`; the Batch 3 evaluator verifies those fingerprints before scoring.

## Frozen decision logic

1. Lexicon evasion detection (URL / website-reference boilerplate) flags the segment.
2. Otherwise, if any KPI/numeric evidence is detected, flag only when semantic similarity to vague references is at least **0.58** and exceeds similarity to quantified references by at least **0.15**.
3. Otherwise, flag when either the lexicon hedging rule or semantic rule fires.
4. The semantic rule uses vague similarity **>= 0.42** and requires vague similarity to exceed quantified similarity.
5. For lexicon hedging, a segment with KPI evidence is not flagged by the lexicon rule. For text over 80 words, hedging density must be at least **0.005**; shorter text with any matched hedging phrase is flagged.

The KPI patterns, lexicon terms, semantic reference examples, sentence splitter, and model name (`all-mpnet-base-v2`) are also part of the freeze, not just the numeric thresholds.

## Evaluation interpretation

- Batches 1 and 2 combine to N=80 and have been used during detector development. Any recomputed metrics are development-set metrics, not held-out performance.
- Their label blinding is unconfirmed because the source CSVs include `model_flagged` and `flag_source`. Keep this caveat with every reported result.
- Batch 3 is a separate 70-row sample. Its predictions must be computed only after the detector freeze, after independent labels are complete and disagreements adjudicated. It was sampled by detector flag-source strata, so document that design when interpreting metrics.
- The current detector exposes a binary decision, not continuous scores. ROC AUC computed from the binary decisions is a coarse binary-score AUC (equivalent to balanced accuracy), not a threshold-independent ranking metric.
- The N=80 and Batch 3 evaluation scripts call `analyze_combined_vagueness()` only. Do not describe their metrics as an evaluation of claim-vs-figure or assurance-gap signals, or of the full integrated four-signal auditor.

## Frozen implementation files

- `src/analysis/vagueness/vagueness_combined.py`
- `src/analysis/vagueness/vagueness_lexicon.py`
- `src/analysis/vagueness/vagueness_semantic.py`

## Frozen N=80 development result (2026-10-18)

User-run output from `scripts/04_greenwashing_detection/evaluate_dev80_frozen.py`:

| Metric | Result |
|---|---:|
| N (batch 1 + batch 2) | 80 (30 + 50) |
| Accuracy | 0.7500 |
| Precision | 0.7073 |
| Recall | 0.7838 |
| F1 | 0.7436 |
| AUC from binary decisions | 0.7524 |

Confusion matrix: TN=31, FP=12, FN=8, TP=29. Labels include 43 not-vague and 37 vague examples. Blinding of these labels is unconfirmed, and the samples were used during engine development; these are development metrics only. The AUC is computed from hard 0/1 predictions and equals balanced accuracy, not a continuous-score ROC AUC. Source fingerprints are recorded in `data/validation/stage4_detector_freeze.json`; raw metrics are in `results/audit/stage4_dev80_frozen_results.json`.
