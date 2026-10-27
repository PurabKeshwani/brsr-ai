# BRSR-AI GRASP — Master Audit Summary

**Audit updated**: 2026-10-19
**Code revision**: unverified; prior embedded Git hash was hard-coded and is not authoritative
**Global rules applied**: No synthetic labels, no post-hoc cherry-picking, no exclusions without pre-stated criterion, every number gets N + CI.

> **Canonical paper-writing table:** use [`stage1_7_final_master_table.md`](stage1_7_final_master_table.md) for the consolidated Stage 1–7 final numbers, Ns, confidence intervals, and caveats. The historical task ledger below is retained for audit trail and may contain superseded values.

> **Dataset version note (2026-10-18):** Stage 2 mappings include explicitly documented AI-generated weak labels, and the user rebuilt the 42,409-row segment splits and then created the company-disjoint split. The Stage 3 seed-99 checkpoint was evaluated on the current company-disjoint test set (N=6,201). Do not describe the AI-generated concept labels as expert-verified. See `results/audit/stage2_ai_mapping_provenance.md` for mapping provenance.

### Current Stage 2 Dataset Snapshot (2026-10-17)

| Source / split | Rows |
|---|---:|
| Section B (`PrincipleAxis`) | 2,479 |
| Section C (concept mappings, including AI weak labels) | 36,513 |
| NotesPrincipleX | 3,417 |
| **Total** | **42,409** |
| Train | 29,683 |
| Validation | 6,358 |
| Test | 6,368 |

The company-disjoint split was rebuilt from these CSVs and is the basis for the recovered seed-99 evaluations below. The exploratory multi-label run uses a grouped variant of this established company partition; it does not create a fresh test cohort.

**Stage 2 caveats and audit results:** labels are taxonomy-derived weak labels, with 29 AI-assisted Section C mappings that have not been expert-verified; Section C contributes 86.1% of the dataset. The current Section B funnel is 41,898 explanatory facts → 25,214 after narrative filtering → 2,479 final rows; 16,684 fail the narrative filter, 18 are same-label duplicates, and 22,717 label entries are dropped in contradictory groups. The old 17,219 count matches no measured current funnel stage and its original query/database snapshot is unavailable, so the historical change remains unresolved. On the recovered seed-99 evaluation of the 6,201-row company-disjoint test, source-wise Top-1 was Section B 63.35% (223/352; CIN-bootstrap 95% CI [56.55%, 69.67%]), Section C 95.15% (5,104/5,364; [94.41%, 95.92%]), and Notes 90.72% (440/485; [86.55%, 94.09%]). A concept-disjoint Section C diagnostic withheld 17/74 concepts and evaluated 1,190 rows from 174 CINs: the concept-disjoint model scored 87.31% Top-1 (1,039/1,190; CIN-bootstrap CI [85.50%, 89.22%]), versus 97.98% for the full-concept baseline, a paired difference of −10.67 pp [−12.36, −8.96]. This indicates a substantial concept/template regularity effect in agreement with weak labels, while not proving human semantic understanding. Checkpoint restoration was verified; the same previously observed holdout was reused, so this is a technical recheck, not a fresh test. Details: `results/audit/stage2_final_audit.md`, `results/audit/stage3_seed99_recovered_full_results.json`, and `results/audit/stage2_concept_disjoint_recovered_results.json`.

**Stage 2 / Stage 3 / Stage 5 checkpoint checks:** the recovered seed-99 model was re-evaluated over all 6,201 company-disjoint test rows; outputs are `stage3_seed99_recovered_full_results.json` and `stage5_company_disjoint_recovered_results.json`. Three concept-disjoint hold-outs (42, 17, 73) are complete: Top-1 mean ± sample SD **81.64% ± 4.92 pp**, Top-2 **95.34% ± 1.31 pp**, macro-F1 **0.6752 ± 0.0170**; full-concept baseline Top-1 **97.07% ± 0.97 pp**. The paired Top-1 difference averaged −15.43 pp (SD 4.22 pp). These are repeat hold-out stability values, not CIs or independent test uncertainty: all use the same underlying company-disjoint test population and seed 42 was previously observed. The exploratory multi-label run is now complete: on the reused 5,934-group test set, Hit@1 93.36%, Hit@2 97.39%, micro-F1 0.8898, macro-F1 0.8782, exact-set match 90.26%; CIN-bootstrap 95% CIs are in `results/audit/stage2_multilabel_results.json`. Recovered single-label baseline scored Hit@1 93.55% and Hit@2 97.81% on the same multi-hot targets, so this is not an across-the-board hit-rate improvement. Different target definition, weak-label provenance, multi-source grouping, and test reuse require exploratory framing. Full interpretation: `results/audit/stage2_final_audit.md`.

---

## Historical Detailed Results Ledger (Use the Canonical Stage 1–7 Table Above)

| Stage | Metric | Old Value | New Value | Split Type | Label Source | N | 95% CI | Script Path | Status |
|---|---|---|---|---|---|---|---|---|---|
| S3 | Top-1 Accuracy | 93.83% | 93.13% | Segment-split (exact-dedup) | XBRL taxonomy | 5,197 | — | `scratch/audit_stage3_non_overlapping.py` | ✅ Done |
| S3 | Top-2 Accuracy | 98.07% | 97.73% | Segment-split (exact-dedup) | XBRL taxonomy | 5,197 | — | `scratch/audit_stage3_non_overlapping.py` | ✅ Done |
| S3 | Top-1 Accuracy | 93.83%* | **93.00%** | **Company-disjoint** (0% CIN overlap) | XBRL + AI weak mappings | 6,201 | [92.04%, 93.89%] (CIN bootstrap) | `results/audit/stage3_stage5_recovered_full_eval.py` | ✅ Seed-99 checkpoint recovered and full test re-evaluated; weak-label caveat |
| S3 | Top-2 Accuracy | 98.07%* | **97.68%** | Company-disjoint | XBRL + AI weak mappings | 6,201 | [97.10%, 98.21%] (CIN bootstrap) | `results/audit/stage3_stage5_recovered_full_eval.py` | ✅ Recovered checkpoint; reuses established test |
| S3 | Macro-F1 | — | **0.9158** | Company-disjoint | XBRL + AI weak mappings | 6,201 | [0.9036, 0.9277] (CIN bootstrap) | `results/audit/stage3_stage5_recovered_full_eval.py` | ✅ Recovered checkpoint; weak-label caveat |
| S3 | Top-1 (TF-IDF sim<0.90) | — | **93.15%** | Segment-split, near-dup filtered | XBRL taxonomy | 4,965 | — | `results/audit/task1_leakage_audit.py` | ✅ Done |
| S3 | Top-1 (TF-IDF sim>0.95 bucket) | — | **95.69%** | Near-verbatim duplicates | XBRL taxonomy | 812 | — | `results/audit/task1_leakage_audit.py` | ✅ Done (expected high) |
| S3 | Top-1 (TF-IDF sim 0.90-0.95) | — | **82.89%** | Near-dup zone | XBRL taxonomy | 76 | — | `results/audit/task1_leakage_audit.py` | ✅ Done |
| S4 | F1 (old engine) | **0.880** | — | Development sample (reported N=30) | Human; blinding unconfirmed | 30 | — | Historical evaluation | ⚠️ Old engine |
| S4 | F1 (old engine) | **0.732** | — | Development batches 1+2 | Human; blinding unconfirmed | 80 | — | Historical evaluation | ⚠️ Old engine; 15 FP, 7 FN reported |
| S4 | F1 (fixed engine, prior report) | — | **0.923 (N uncertain; likely 30)** | Development sample; likely N=30 | Human; blinding unconfirmed | Unverified | — | Historical evaluation | ⚠️ Do not report as N=80 |
| S4 | F1 (fixed engine, tuning run) | — | **1.000** | In-sample threshold-tuning subset | Human; blinding unconfirmed | 30 | — | Historical tuning run | ❌ In-sample; not a validation result |
| S4 | Accuracy (frozen text-vagueness engine) | — | **0.750** | Development batches 1+2 | Human; blinding unconfirmed | 80 | — | `scripts/04_greenwashing_detection/evaluate_dev80_frozen.py` | ⚠️ Development only |
| S4 | Precision / Recall | — | **0.707 / 0.784** | Development batches 1+2 | Human; blinding unconfirmed | 80 | — | `scripts/04_greenwashing_detection/evaluate_dev80_frozen.py` | ⚠️ Development only |
| S4 | F1 (frozen text-vagueness engine) | — | **0.744** | Development batches 1+2 | Human; blinding unconfirmed | 80 | — | `scripts/04_greenwashing_detection/evaluate_dev80_frozen.py` | ⚠️ Development only |
| S4 | AUC (binary predictions) | — | **0.752** | Development batches 1+2 | Human; blinding unconfirmed | 80 | — | `scripts/04_greenwashing_detection/evaluate_dev80_frozen.py` | ⚠️ Equals balanced accuracy; not continuous-score AUC |
| S4 | Accuracy / Precision / Recall | — | **0.729 / 0.600 / 0.808** | Batch 3 AI-label comparison | AI-generated text-only labels | 70 | — | `scripts/04_greenwashing_detection/evaluate_stage4_batch3_ai_annotations.py` | ⚠️ Exploratory only; not human-held-out |
| S4 | F1 (frozen text-vagueness engine vs AI labels) | — | **0.689** | Batch 3 AI-label comparison | AI-generated text-only labels | 70 | — | `scripts/04_greenwashing_detection/evaluate_stage4_batch3_ai_annotations.py` | ⚠️ Not ground truth; no kappa |
| S4 | AUC (binary predictions vs AI labels) | — | **0.745** | Batch 3 AI-label comparison | AI-generated text-only labels | 70 | — | `scripts/04_greenwashing_detection/evaluate_stage4_batch3_ai_annotations.py` | ⚠️ Equals balanced accuracy; not continuous-score AUC |
| S4 | F1 (held-out vagueness subdetector) | — | **BLOCKED** | Batch 3 (N=70) | Two independent human raters + adjudication | 70 | Pending | `results/audit/task4_batch3_eval.py` | ❌ Needs labels |
| S5 | Top-1 (zero-shot MPNet hybrid) | 44.27% (legacy N=393) | **67.63% (4,194/6,201)** | Stage 3 company-disjoint test | XBRL + AI weak mappings | 6,201 / 175 CINs | [66.45%, 68.93%] (CIN bootstrap) | `results/audit/stage3_stage5_recovered_full_eval.py` | ⚠️ Reuses test; legacy baseline not comparable |
| S5 | Top-2 (zero-shot MPNet hybrid) | 60.05% (legacy N=393) | **83.34% (5,168/6,201)** | Stage 3 company-disjoint test | XBRL + AI weak mappings | 6,201 / 175 CINs | [82.31%, 84.38%] (CIN bootstrap) | `results/audit/stage3_stage5_recovered_full_eval.py` | ⚠️ Reuses test; legacy baseline not comparable |
| S5 | Top-1 (supervised transfer) | 74.55% (legacy N=393; compromised/unverified) | **93.00% (5,767/6,201)** | Stage 3 company-disjoint test | XBRL + AI weak mappings | 6,201 / 175 CINs | [92.04%, 93.89%] (CIN bootstrap) | `results/audit/stage3_stage5_recovered_full_eval.py` | ⚠️ Weak labels; not independent ground truth |
| S5 | Top-2 (supervised transfer) | 84.99% (legacy N=393; compromised/unverified) | **97.68% (6,057/6,201)** | Stage 3 company-disjoint test | XBRL + AI weak mappings | 6,201 / 175 CINs | [97.10%, 98.21%] (CIN bootstrap) | `results/audit/stage3_stage5_recovered_full_eval.py` | ⚠️ Weak labels; not independent ground truth |
| S5 | Paired Top-1 lift (supervised vs zero-shot) | — | **+25.37 pp** | Same company-disjoint test rows | XBRL + AI weak mappings | 6,201 / 175 CINs | [+24.02, +26.71 pp] (paired CIN bootstrap) | `results/audit/stage3_stage5_recovered_full_eval.py` | ⚠️ Supervised transfer comparison, not causal alignment gain |
| S6 | Pearson r | 0.631 | **0.6314** | N=20 real human ratings | Human (UNVERIFIABLE anchoring) | 20 | [0.268, 0.852] | `results/audit/task5_stage6_audit.py` | ✅ Done |
| S6 | Spearman ρ | 0.629 | **0.6285** | N=20 real human ratings | Human | 20 | [0.232, 0.854] | `results/audit/task5_stage6_audit.py` | ✅ Done |
| S6 | Kendall τ | — | **0.4534** | N=20 real human ratings | Human | 20 | — (p=0.0057) | `results/audit/task5_stage6_audit.py` | ✅ Done |
| S6 | MAE | — | **12.16** | N=20 real human ratings | Human | 20 | — | `results/audit/task5_stage6_audit.py` | ✅ Done |
| S6 | Pearson r (ex-Zensar, post-hoc) | 0.785 | **0.7379** | N=19 (Zensar excluded) | Human | 19 | [0.516, 0.886] | `results/audit/task5_stage6_audit.py` | ✅ Declared sensitivity |
| S6 | Pearson r (ex-Geojit, post-hoc) | — | **0.6735** | N=19 (Geojit BFSI excluded) | Human | 19 | [0.297, 0.883] | `results/audit/task5_stage6_audit.py` | ✅ Declared sensitivity |
| S6 | Pearson r (ex-both, post-hoc) | 0.785 | **0.7847** | N=18 (both excluded) | Human | 18 | [0.567, 0.909] | `results/audit/task5_stage6_audit.py` | ✅ Declared sensitivity |
| S6 | LTI r=0.9482 | 0.9482 | **QUARANTINED** | N=50 synthetic labels | Formula 0.15C+0.45Sp+0.20Cl+0.20SDG | 50 | INVALID | `data/quarantine/` | ❌ Fabricated |

---

## TASK 0 — Label Provenance Summary

### Historical Dataset Inventory (pre-2026-10-17 rebuild; not current)

| File | Rows | MD5 (12) | Label Source | Status |
|---|---|---|---|---|
| `data/training/train.csv` | 27,272 | `d82f9533a5ed` | XBRL taxonomy (PrincipleAxis + concept mapping) | Historical |
| `data/training/val.csv` | 5,841 | `620977ca06b2` | XBRL taxonomy | Historical |
| `data/training/test.csv` | 5,853 | `af6efbec8ac8` | XBRL taxonomy | Historical (company overlap) |
| `data/training_company_split/train.csv` | 27,422 | `fb0e54c6bb93` | XBRL taxonomy, company-disjoint | Stale; regenerate |
| `data/training_company_split/val.csv` | 5,823 | `e76c077af370` | XBRL taxonomy, company-disjoint | Stale; regenerate |
| `data/training_company_split/test.csv` | 5,721 | `89201b663012` | XBRL taxonomy, company-disjoint | Stale; regenerate |
| `data/validation/human_score_validation.csv` | 20 | `b4bcf1feb232` | **Real human ratings** | ✅ Active |
| `data/validation/vagueness_validation_sample.csv` | 30 | `1962ea72c41b` | **Human; blinding unconfirmed** | ⚠️ Dev set |
| `data/validation/vagueness_validation_sample_batch2.csv` | 50 | `9d3e8b99c815` | **Human; blinding unconfirmed** | ⚠️ Dev set |
| `data/validation/vagueness_validation_sample_batch3.csv` | 70 | `9eb49f1d5848` | **BLOCKED: unlabeled** | ❌ Needs human |
| `data/validation/human_score_validation_n50.csv` | 50 | `20dc2f9e6db9` | **SYNTHETIC** (30/50 formula-generated) | ❌ Quarantined |
| `data/validation/lti_calibration_results_n50.csv` | 50 | `397525ad5f7e` | **SYNTHETIC** (derived from n50) | ❌ Quarantined |

### Historical Source Breakdown (38,966 total; pre-2026-10-17 rebuild)

> This source breakdown belongs to the pre-rebuild dataset and is retained only for audit history. Use the current 42,409-row snapshot above for paper reporting.

| Source | Count | % | Label Rule |
|---|---|---|---|
| section_c | 33,022 | 84.7% | Concept name → principle (44-entry dict, SEBI BRSR Annexure I) |
| notes_principle | 3,417 | 8.8% | `NotesPrinciple{N}ExplanatoryTextBlock` → label N-1 |
| section_b | 2,527 | 6.5% | `fact.dimensions["PrincipleAxis"]` XBRL dimension |

---

## Historical TASK 1 — Stage 3 Segment-Split Leakage Audit Findings

> This section describes the superseded segment-split dataset (N=5,853 test; 100% of test CINs also appeared in train). Do not use its segment-split scores as final company-generalization results. Use the recovered company-disjoint N=6,201 results above and in the canonical Stage 1–7 table.

| Check | Finding | Impact |
|---|---|---|
| Company overlap (segment-split) | 1,146/1,146 test CINs in train (**100%**) | Model saw other disclosures from EVERY test company |
| Test rows from shared companies | 5,853/5,853 (**100%**) | All test rows are within-company-distribution |
| Sliding window overlap | **None at build time** (full XBRL facts used) | No window-level leakage |
| Shared (cin, source) combos train∩test | 1,663 | Different segments from same company+source |
| Exact text duplicates | 656 (~11.2%) | Cross-company statutory boilerplate |
| Company-disjoint test set | 0% company overlap (GroupShuffleSplit by CIN) | ✅ Built, ready for Task 2 |

### TF-IDF Similarity Buckets (Segment-Split Test)

| Bucket | N | % | Top-1 | Top-2 | Macro-F1 |
|---|---|---|---|---|---|
| <0.70 (distinct) | 4,505 | 77.0% | **93.58%** | 98.27% | 0.9302 |
| 0.70–0.80 | 254 | 4.3% | 90.55% | 97.24% | 0.8958 |
| 0.80–0.90 | 206 | 3.5% | 86.89% | 93.20% | 0.8633 |
| 0.90–0.95 (near-dup) | 76 | 1.3% | 82.89% | 92.11% | 0.8120 |
| >0.95 (near-verbatim) | 812 | 13.9% | **95.69%** | 98.40% | 0.8677 |
| **<0.90 (strict subset)** | **4,965** | **84.8%** | **93.15%** | 98.01% | 0.9258 |
| **All test** | **5,853** | **100%** | **93.37%** | 97.98% | 0.9266 |

> The >0.95 bucket has 812 rows of near-verbatim statutory boilerplate — model scores higher there (95.69%) due to memorized phrasing patterns, NOT because the examples are easier to classify. The 0.90-0.95 bucket (76 rows) is the hardest at 82.89%.

> [!IMPORTANT]
> **The 93.83% Top-1 is within-company-distribution accuracy, NOT out-of-sample company generalization.** The correct number requires TASK 2 retrain on the company-disjoint split.

---

## TASK 2 — Company-Level Retrain Status

- **Script**: [`results/audit/task2_company_level_retrain.py`](file:///d:/brsr-ai-phase0-1/brsr-ai/results/audit/task2_company_level_retrain.py)
- **Status**: ✅ Five-seed run completed; selected seed-99 checkpoint restored and verified
- **Recovered seed-99 full-test result**: Top-1 93.00% (95% CIN-cluster bootstrap CI [92.04%, 93.89%]); Top-2 97.68% ([97.10%, 98.21%]); Macro-F1 0.9158 ([0.9036, 0.9277]), test N=6,201. See `stage3_seed99_recovered_full_results.json`.
- **Best seed**: 99, selected by validation macro-F1; validation macro-F1 mean across five seeds 0.9175 ± 0.0025
- **Checkpoint recovery note**: The selected checkpoint's 50 LayerNorm `gamma/beta` aliases were remapped to `weight/bias`, loaded strictly, and verified tensor-for-tensor after save/reload. The earlier pre-recovery warning is resolved for the recovered seed-99 checkpoint. The MLM-head mismatch when initializing a sequence classifier from the domain-adapted masked-language-model encoder is an expected architecture difference.
- **Provenance note**: The result JSON contains a hard-coded historical Git hash, not a verified revision identifier for this run.
- **Command**: `python results/audit/task2_company_level_retrain.py`
- **Output**: `results/audit/task2_company_retrain_results.json`, `results/audit/stage3_trials.csv`

**Config**: Domain-Adapted BERT, LR=2e-5, 5 epochs, class weights, batch=16 (4×4 accum), 5 seeds.  
**Test**: Current recovered seed-99 evaluation uses `data/training_company_split/test.csv` (N=6,201, 0% CIN overlap). The older N=5,721 report is a stale split and is not the final result.
**Reporting**: Mean±std across seeds, cluster-bootstrap 95% CI by CIN.

---

## TASK 3 — Stage 5 Regulatory Alignment (Audit complete; details summarized in the canonical Stage 1–7 table)

The historical n=393 results are not cleared for reporting. The user-run reconstruction matched 393 segments, but those rows came from only **52 contributing companies**, not 100. Against the Stage 3 split, 258 rows from 37 companies overlap train (111 exact normalized text hashes), 84 rows from 8 companies overlap validation (28 hashes), and 51 rows from 7 companies overlap test (26 hashes). The prior Stage 5 code loaded `data/models/brsr_principle_classifier/final_model_unweighted_93.68`, not the Stage 3 company-disjoint seed-99 checkpoint. The company-disjoint re-evaluation is complete on the same Stage 3 test set for both systems (N=6,201; 175 CINs): zero-shot MPNet hybrid Top-1 67.63% [66.45%, 68.93%], Top-2 83.34% [82.31%, 84.38%]; recovered supervised transfer Top-1 93.00% [92.04%, 93.89%], Top-2 97.68% [97.10%, 98.21%]. The paired CIN-cluster bootstrap Top-1 difference is +25.37 pp [24.02, 26.71]. Checkpoint recovery was verified. These results compare supervised transfer to zero-shot embedding, not an isolated alignment-scoring gain, and use current weak labels. Full audit: `results/audit/stage5_final_audit.md`.

---

## TASK 4 — Stage 4 Greenwashing

| Item | Status | Details |
|---|---|---|
| Prior fixed-engine F1 | ⚠️ 0.923, N uncertain (likely 30) | Historical result; frozen N=80 result is separately reported above |
| Frozen text-vagueness subdetector N=80 | ✅ F1 0.744 | Accuracy 0.750, precision 0.707, recall 0.784, hard-label AUC 0.752; batches 1+2 were used during development and label blinding is unconfirmed |
| Batch 3 export (70 segments) | ✅ Done | `data/validation/vagueness_validation_sample_batch3.csv` |
| Separate blind Batch 3 rater sheets | ✅ Generated | `data/labeling_sheets/stage4_batch3_rater_A.csv` and `stage4_batch3_rater_B.csv`; no model signals included |
| AI text-only annotations | ✅ Prepared, transparently attributed | `data/labeling_sheets/stage4_batch3_ai_annotations.csv`; not human labels and not usable for Cohen's kappa or human-held-out metrics |
| AI-label comparison | ✅ Completed, exploratory | N=70 descriptive point estimates; accuracy 0.729, precision 0.600, recall 0.808, F1 0.689; no CI calculated; confusion matrix TN=30, FP=14, FN=5, TP=21; `results/audit/stage4_batch3_ai_comparison.json` |
| Human-held-out Batch 3 evaluation | ❌ **BLOCKED: no human raters** | No independent human labels, adjudication, or Cohen's kappa; AI comparison does not substitute for these |
| Original batch labeling confirmation | ⚠️ UNVERIFIABLE | `model_flagged` + `flag_source` columns present in export CSVs; whether raters saw them is unknown |
| Full four-signal integrated evaluation | ❌ Not available from current labels | Current N=80/N=70 text evaluator measures only lexicon + semantic vagueness, not claim-vs-figure or assurance-gap signals |
| XGBoost target F1 0.94–0.96 | ❌ Not achieved | Experimental only; do not report as achieved |

> [!WARNING]
> Batch 3 export (`vagueness_validation_sample_batch3.csv`) contains `model_flagged` and `flag_source` columns. Give raters only the separate sheets generated by `export_stage4_independent_rater_sheets.py`; each contains ID, company, text, and one blank label column. The N=80 and Batch 3 F1 metrics evaluate only the text vagueness subdetector, not the full four-signal auditor.

> Rater instructions: `data/labeling_sheets/stage4_batch3_rater_instructions.md`. Send each rater only their own CSV and the shared instructions. Do not show detector predictions or the other rater's answers.

---

## TASK 5 — Stage 6 Transparency Score

Full audit: `results/audit/stage6_audit.md`. The fixed SEBI formula and current N=20 results are documented below. Human-label blinding remains unconfirmed. The 30 new summaries and corrected Zensar summary have been scored by AI only because human raters were unavailable; see `data/labeling_sheets/stage6_ai_annotations.csv` and its provenance note. These annotations are exploratory and do not constitute human validation, replace the historical Zensar human rating, or establish a real-human N=50. `data/labeling_sheets/stage6_new_ratings.csv` contains model scores and is private; it must not be given to raters.

### Headline (N=20, Fixed SEBI Heuristic 40-30-20-10)

| Metric | Value | 95% Bootstrap CI | p-value |
|---|---|---|---|
| Pearson r | **0.6314** | [0.268, 0.852] | 0.0028 |
| Spearman ρ | **0.6285** | [0.232, 0.854] | 0.0030 |
| Kendall τ | **0.4534** | — | 0.0057 |
| MAE | **12.16** | — | — |
| RMSE | **15.19** | — | — |
| R² | **39.9%** | — | — |

### Declared Post-Hoc Sensitivities (not headline)

| Cohort | Criterion | Pearson r | 95% CI |
|---|---|---|---|
| N=19 (ex-Zensar) | URL-redirect extraction bug (data artifact, not model) | 0.7379 | [0.516, 0.886] |
| N=19 (ex-Geojit) | BFSI sector structural non-applicability of mfg KPIs | 0.6735 | [0.297, 0.883] |
| N=18 (ex-both) | Both criteria above | 0.7847 | [0.567, 0.909] |

### Exploratory Only

| Analysis | Result | Note |
|---|---|---|
| LOOCV weight-tuned (N=20) | r = 0.4993 | Lower than SEBI fixed — N=20 too small for reliable weight learning |

### Issues Diagnosed

| Issue | Finding |
|---|---|
| **Anchoring bias** | `ai_transparency_score` column co-occurs with `human_score` in `data/validation/human_score_validation.csv`; whether the rater saw it is unconfirmed. |
| **New-rating sheet exposure** | `data/labeling_sheets/stage6_new_ratings.csv` contains `transparency_score` beside the blank human-score column. Keep private; use the separate blind packet export. |
| **Zensar URL artifact** | Old packet included URL-heavy policy links due to the extraction/sampling bug. A fresh cleaned narrative and human re-rating are still needed. |
| **URL artifacts across all 20** | 8-9 companies have bare-URL facts but current export code skips them for human summaries — artifact is in the transparency score computation, not human summary. |
| **Synthetic n50** | 48/50 `human_score` values in n50 are formula-generated → quarantined. |

### QUARANTINED FILES

- `data/quarantine/human_score_validation_n50.csv` — synthetic labels (48/50 rows)
- `data/quarantine/lti_calibration_results_n50.csv` — Ridge regression on synthetic labels

---

## BLOCKED: Needs Human

| ID | Task | File | Action Needed |
|---|---|---|---|
| BLOCKED-1 | S4 Batch 3 | `data/labeling_sheets/stage4_batch3_clean.csv` | Two raters fill `human_label_rater_A`, `human_label_rater_B`; adjudicate; compute Cohen's kappa |
| BLOCKED-2 | S4 dev labeling confirmation | `data/validation/vagueness_validation_sample.csv` | Team confirms whether `model_flagged`/`flag_source` were visible during labeling |
| BLOCKED-3 | S6 human validation | `data/labeling_sheets/stage6_new_ratings_blind.csv` | No human raters available. AI annotations exist separately but cannot replace human labels or count toward N=50 real-human validation |
| BLOCKED-4 | S3 Section C spot-check | `data/labeling_sheets/stage3_section_c_spot_check.csv` | Expert verifies 207-row sample of concept→principle mapping |
| BLOCKED-5 | S6 Zensar human re-rating | `data/labeling_sheets/stage6_zensar_rerating_blind.csv` | Corrected summary has AI annotation only; human re-rating remains unavailable. Do not replace old human score with AI score |

---

## Claims We CAN Make

1. **Stage 3**: 93.00% Top-1 (95% CIN-cluster bootstrap CI [92.04%, 93.89%]) on 6,201 company-disjoint test segments; Macro-F1 0.9158 (95% CI [0.9036, 0.9277]). Selected seed-99 checkpoint restoration was verified; labels include AI-generated weak mappings, and this is a re-evaluation of the established test set.
2. **Stage 3**: Company-disjoint split has 0% CIN overlap across train, validation, and test; test contains 6,201 rows from 175 companies.
3. **Stage 4 (development only)**: Frozen text-vagueness subdetector F1=0.744 on N=80 (accuracy 0.750, precision 0.707, recall 0.784). Batches informed detector development and label blinding is unconfirmed. The prior 0.923 has uncertain N (likely 30). Neither figure evaluates the full four-signal auditor or held-out Batch 3.
4. **Stage 4 (exploratory AI-label comparison)**: Frozen text-vagueness subdetector F1=0.689 (accuracy 0.729, precision 0.600, recall 0.808; N=70) against explicitly AI-generated text-only annotations. This is not human-validated, not gold-standard performance, and not the full four-signal auditor. No Cohen's kappa is available.
5. **Stage 6**: Pearson r=0.6314 (N=20, 95% CI [0.268, 0.852], p=0.0028) using real human ratings and SEBI heuristic weights; blinding/anchoring remains unconfirmed.
6. **Stage 6 AI annotations**: 31 narrative-only AI scores (30 new summaries + corrected Zensar) are available in `data/labeling_sheets/stage6_ai_annotations.csv` for exploratory descriptive use only; they are not human ratings, ground truth, independent validation, or a real-human N=50.
7. **Stage 6**: Post-hoc sensitivity r=0.7847 (N=18, excluding Geojit on BFSI non-applicability criterion AND Zensar on extraction bug criterion).

## Claims We CANNOT Make

1. ❌ **93.83%** as out-of-sample company generalization — it is within-company-distribution and belongs to an earlier dataset version.
2. ❌ **r=0.9482** (LTI calibrated) — synthetic labels, quarantined.
3. ❌ **F1=0.923 as an N=80 or held-out result** — its N is uncertain (likely 30), and it is not a held-out Batch 3 result.
4. ❌ **"Completeness Fallacy" weights** (0.45 Sp, 0.36 Cl, 0.13 Comp) — learned from synthetic labels.
5. ❌ **Anchoring-free human ratings** — unverifiable from file contents.
6. ❌ Any headline estimate without its N and appropriate uncertainty; the AI-label comparison above is explicitly a descriptive point estimate without a CI.
7. ❌ Stage 4's AI-label comparison as human-validated held-out performance, ground truth, or inter-rater reliability; Cohen's kappa is unavailable.
8. ❌ Stage 6 AI annotations as human labels, Cohen's kappa, or independent validation of the transparency formula.

---

## Next Steps (in priority order)

1. **[DONE]** Seed-99 selected checkpoint LayerNorm recovery was verified with strict loading and exact save/reload tensor checks. Full test re-evaluation completed for Stage 3 and Stage 5; outputs are `stage3_seed99_recovered_full_results.json` and `stage5_company_disjoint_recovered_results.json`.
2. **[DONE]** Three concept-disjoint hold-outs completed with strict selected-checkpoint restoration; details are in `stage2_concept_disjoint_repeats_results.json`. **[DONE — exploratory]** Multi-label dataset/model completed with strict selected-checkpoint restoration; report separately from the single-label classifier and retain the existing-test/weak-label caveats. Details: `stage2_multilabel_results.json`.
3. Stage 4 AI-label comparison is complete as an exploratory result. If human raters remain unavailable, report only the transparent AI-label comparison and state that human-held-out evaluation is unavailable; do not call Stage 4 human-validated or report kappa.
4. **[USER action needed]** Confirm whether batch 1+2 labelers saw `model_flagged` / `flag_source`.
5. Only if two independent human raters later become available: label Batch 3 blind, adjudicate every row, then run `task4_batch3_eval.py` exactly once for the held-out text-vagueness result.
6. Human Stage 6 validation is unavailable. If independent human raters later become available, collect 30 new blind ratings and one corrected Zensar re-rating; keep the score-bearing CSV private and never represent current AI annotations as human labels.
7. After genuine human labels return, use a predeclared calibration/evaluation split; preserve the fixed SEBI formula as primary and report any fitted weights separately as exploratory. State small N, old-cohort blinding uncertainty, Geojit sector mismatch, and single-rater-source limitations.
9. After all numbers locked: update paper `CAPSTONE_RESEARCH_PAPER_LATEST`.
