# Stages 1–7: Consolidated Final Results and Verification Status

**Prepared:** 2026-10-19  
**Purpose:** One source of truth for paper-writing values. Use the listed current values and caveats; do not copy superseded historical numbers as final metrics.

## Master table

| Stage | Primary result to report | N / evaluation population | 95% CI | Status and required wording |
|---|---|---:|---|---|
| **1 — XBRL ingestion** | No audited accuracy estimate. The project pivoted away from PDF extraction after an initial real-filing PDF extraction check estimated about **70–75% row-level accuracy**. The README reports **1,164 of 1,276 companies (91.2%)** fully ingested and scored; this is not a current audited coverage count. | PDF pilot N not recorded here; coverage denominator 1,276 companies | Not available | Describe XBRL as the structured source. Treat the PDF pilot estimate and 1,164-of-1,276 coverage as historical project-reported values, not current validated performance. Do not mix in unverified filing totals. |
| **2 — Dataset / labels** | **42,409** clean single-label samples: Section B 2,479; Section C 36,513; NotesPrincipleX 3,417. Company-disjoint seed-99 source-wise Top-1 agreement: B **63.35%**, C **95.15%**, Notes **90.72%**. | B n=352 / 71 CINs; C n=5,364 / 174 CINs; Notes n=485 / 103 CINs | B [56.55%, 69.67%]; C [94.41%, 95.92%]; Notes [86.55%, 94.09%] (CIN bootstrap) | These are agreements with taxonomy-derived weak labels. Section C is 86.1% of the dataset; the concept-disjoint/repeat diagnostics show concept/template regularity. Do not call them expert-validated semantic accuracy. |
| **2 — Multi-label redesign (exploratory)** | Hit@1 **93.36%**; Hit@2 **97.39%**; micro-F1@0.5 **0.8898**; macro-F1@0.5 **0.8782**; exact-set match **90.26%**. | n=5,934 grouped company-text examples; 175 test CINs | Hit@1 [92.54%, 94.11%]; Hit@2 [96.77%, 97.92%]; micro-F1 [0.8743, 0.9035]; macro-F1 [0.8606, 0.8942] (CIN bootstrap) | Different multi-hot target; grouped labels are unioned and may combine reused boilerplate. Existing company-disjoint test reused. Baseline Hit@1/2 were 93.55%/97.81%, so do not claim across-the-board gains. |
| **3 — Principle classifier** | Recovered seed-99 Top-1 **93.00%** (5,767/6,201); Top-2 **97.68%** (6,057/6,201); macro-F1 **0.9158**. | n=6,201 segments; 175 CINs; company-disjoint | Top-1 [92.04%, 93.89%]; Top-2 [97.10%, 98.21%]; macro-F1 [0.9036, 0.9277] (CIN bootstrap) | Checkpoint-7460 recovered by strict remapping of 50 LayerNorm aliases and exact save/reload verification. Existing test re-evaluated, not a fresh cohort. Labels are weak labels, not independent human ground truth. |
| **4 — Greenwashing / vagueness detector** | Frozen text-vagueness subdetector, batches 1+2: accuracy **0.750**, precision **0.707**, recall **0.784**, F1 **0.744**. Batch 3 AI-label comparison: accuracy **0.729**, precision **0.600**, recall **0.808**, F1 **0.689**. | Development n=80; exploratory AI-label comparison n=70 | Not calculated | Not the complete four-signal auditor and not human-held-out validation. Batch 1+2 label blinding is unconfirmed; Batch 3 labels are AI-generated. No Cohen’s kappa. XGBoost target was not achieved. |
| **5 — Regulatory alignment** | Recovered supervised transfer Top-1 **93.00%**, Top-2 **97.68%**; zero-shot MPNet hybrid Top-1 **67.63%**, Top-2 **83.34%**. Paired Top-1 difference **+25.37 percentage points**. | n=6,201 same test segments; 175 CINs | Supervised Top-1 [92.04%, 93.89%], Top-2 [97.10%, 98.21%]; zero-shot Top-1 [66.45%, 68.93%], Top-2 [82.31%, 84.38%]; paired Top-1 difference [+24.02, +26.71] pp (CIN bootstrap) | Frame as supervised transfer vs zero-shot embedding, not a causal gain from alignment scoring. Reuses Stage 3 test and weak labels; does not establish regulatory compliance. The legacy N=393 result is not cleared. |
| **6 — Transparency score** | Fixed SEBI-weight formula vs real human ratings: Pearson **r=0.6314**; Spearman **ρ=0.6285**; MAE **12.16**; RMSE **15.19**; R² **0.3986**. | n=20 human-rated companies | Pearson [0.2683, 0.8519]; Spearman [0.2321, 0.8540] | Real-human cohort, but whether the rater saw `ai_transparency_score` is unconfirmed. Small N, one rater source, and sector mismatch caveats. Exclusion cohorts are post-hoc sensitivities; synthetic N=50 metrics remain quarantined. |
| **7 — API / runtime integration** | **No model-performance metric reported.** `GET /companies/{name}/compliance-mapping` returned method `recovered_seed99_supervised_classifier` and the recovered checkpoint path for 360 ONE WAM LIMITED. Its returned filing summary was 89.17%; this is a company-specific model output, not validation accuracy. | One successful API request; not an evaluation cohort | Not applicable | Runtime checkpoint loading verified by the user on 2026-10-19. The endpoint fails closed instead of silently falling back to zero-shot. Output is classifier probability against weak labels, not regulatory compliance. |

## Stage 2 concept-disjoint diagnostic

For the concept-disjoint Section C check, the one-holdout recovered model scored Top-1 **87.31%** (1,039/1,190; CIN-bootstrap 95% CI [85.50%, 89.22%]) and Top-2 **96.64%**. The full-concept baseline scored Top-1 **97.98%**; paired difference **−10.67 pp** (95% CI [−12.36, −8.96]). Across three concept holdouts, mean ± sample SD was Top-1 **81.64% ± 4.92 pp**, Top-2 **95.34% ± 1.31 pp**, macro-F1 **0.6752 ± 0.0170**. Those SDs describe variation across three runs, not confidence intervals; all runs reuse the same company-disjoint test population.

## Provenance and reporting rules

- All intervals above are the reported cluster/bootstrap confidence intervals where available. “Not available” means no defensible CI was produced; do not infer one from rounded metrics.
- Stage 3 and Stage 5 reuse the same existing company-disjoint test set. Stage 2 multi-label and concept-disjoint runs reuse that test population or a subset; none is a new external cohort.
- Stage 2/3/5 labels are taxonomy-derived weak labels, including AI-assisted Section C mappings without independent expert validation.
- Company disjointness here applies to supervised fine-tuning. The MLM corpus builder reads narratives from all companies; checkpoint-specific pretraining membership has not been verified. Do not claim the legacy encoder had no unsupervised exposure to validation/test company text. New improvement runs must document encoder corpus membership.
- Stage 4 and Stage 6 contain no completed independent human-held-out validation for their newer cohorts. Keep AI annotations explicitly identified as AI-generated.
- Do not report quarantined Stage 6 synthetic N=50 correlations or historical Stage 4 tuning metrics as validation results.

## Artifacts

- Stage 2: `stage2_final_audit.md`, `stage2_multilabel_results.json`, `stage2_concept_disjoint_repeats_results.json`
- Stage 3: `stage3_company_retrain_audit.md`, `stage3_seed99_recovered_full_results.json`
- Stage 4: `stage4_final_audit.md`, `stage4_dev80_frozen_results.json`, `stage4_batch3_ai_comparison.json`
- Stage 5: `stage5_final_audit.md`, `stage5_company_disjoint_recovered_results.json`
- Stage 6: `stage6_audit.md`, `task5_stage6_results.json`
- Stage 7 route and model path: `src/api/routes.py`, `src/api/schemas.py`, `src/analysis/compliance/compliance_mapper.py`

## Exclude from paper headlines

Do not report these as final validated results: 93.83%, 98.07%, 0.9341, 96.66% calibration, 98–99% sliding-window results, legacy Stage 5 74.55%/84.99%, Stage 4 F1 0.923 or in-sample F1 1.000, Stage 6 r=0.9482, “Completeness Fallacy” weights, historical Section B count 17,219, or the unachieved XGBoost F1 target 0.94–0.96. They are stale, compromised, in-sample, synthetic, or otherwise unsupported for the paper claims.
