# Stage 2 Final Audit — Concept-to-Principle Labels and Dataset Build

**Audit date:** 2026-10-18  
**Status:** Accounting, source-wise held-out evaluation, and three-holdout concept-disjoint stability diagnostic complete; historical count provenance remains unresolved. Labels include AI-generated weak mappings and have not been independently expert-validated.

## Scope

Stage 2 checks how BRSR narrative facts receive one of the nine NGRBC principle labels and rebuilds the train, validation, and test CSVs after correcting and extending the concept map.

## Changes made

- Corrected the value-chain statutory-dues concept from P7 to P3.
- Added three direct BRSR concept mappings: end-of-life plastics reclamation to P2, and two value-chain safety corrective-action concepts to P3.
- Added 29 AI-generated weak mappings for previously unmapped concepts. Existing curated labels take precedence when mappings overlap.
- Kept nine generic, cross-cutting, or case-specific concepts out of single-principle training labels because the concept alone does not identify a reliable unique principle.
- Did not fabricate Section C labels for P7. P7 examples remain available from other sources, including PrincipleAxis and NotesPrinciple7.
- Added a decision ledger and methodology note in `data/labeling_sheets/stage2_concept_review/ai_decisions.csv` and `results/audit/stage2_ai_mapping_provenance.md`.

## Rebuilt dataset

The user ran `scripts/03_bert_training/build_training_dataset.py` with `.venv-ml`. Its output reported:

| Source or split | Rows |
|---|---:|
| Section B (`PrincipleAxis`) | 2,479 |
| Section C (concept map, including AI weak labels) | 36,513 |
| NotesPrincipleX | 3,417 |
| **Total clean labeled samples** | **42,409** |
| Train | 29,683 |
| Validation | 6,358 |
| Test | 6,368 |

Source counts and split counts each sum to 42,409. The builder also reported 36,491 noise-filtered facts and 2,640 contradictory-label groups dropped.

| Principle | Rows |
|---|---:|
| P1 | 5,015 |
| P2 | 5,566 |
| P3 | 11,835 |
| P4 | 3,128 |
| P5 | 3,095 |
| P6 | 5,749 |
| P7 | 543 |
| P8 | 2,475 |
| P9 | 5,003 |

## Audit verdict

**Pass for dataset build and accounting; fail for label-quality claims.** The user-provided builder output confirms the three sources sum to the clean dataset total and the three splits sum to the same total. Per-principle counts also sum to 42,409. The recovered seed-99 Section B held-out accuracy is 63.35%, while most data are concept-mapped Section C with 95.15% agreement; these results do not support presenting 93.00% overall agreement as semantic principle understanding.

**Weak-label quality remains unverified.** The build output confirms that the builder completed and gives counts; it does not independently establish that every AI-generated mapping is semantically correct. No expert review or blind mapping spot-check was completed. Report these assignments as AI-generated taxonomy weak labels, not human annotations or ground truth.

**Current Section B count funnel (current database, user-run audit):** 149,770 facts have a recognized `PrincipleAxis` across all concepts; 41,898 are `ExplanatoryTextBlock` facts; 16,684 fail the current narrative filter, leaving 25,214 clean Section B candidates. Among those, 18 are repeated same-label candidates and 22,717 label entries belong to contradictory `(company, concept, cleaned text)` groups, leaving 2,479 Section B rows. Reconciliation: `25,214 - 18 - 22,717 = 2,479`. The contradiction drops explain most of the current builder's Section B reduction after filtering.

The historical 17,219 count does not equal any measured stage in the current database funnel (including the 149,770 all-concept PrincipleAxis count, 41,898 explanatory candidates, 25,214 clean candidates, or 2,479 final rows). Its original query, extraction date, and database snapshot are unavailable, so the specific historical 17,219-to-2,479 change cannot be attributed definitively. The current pipeline's own reduction is reconciled above.

**Company-disjoint source-wise test result (Stage 3 seed-99 checkpoint):**

| Source | Correct / N | Companies | Top-1 accuracy | 95% CIN-cluster bootstrap CI | Macro-F1 |
|---|---:|---:|---:|---:|---:|
| Section B (`PrincipleAxis`) | 223 / 352 | 71 | 63.35% | [56.55%, 69.67%] | 0.6373 |
| Section C (concept map) | 5,104 / 5,364 | 174 | 95.15% | [94.41%, 95.92%] | 0.8403 |
| NotesPrincipleX | 440 / 485 | 103 | 90.72% | [86.55%, 94.09%] | 0.8915 |

The cleanest source, Section B, is far below 90%; the requested diagnostic therefore does **not** allay the template-recovery concern. Section C supplies 86.1% of the dataset and its label is determined from the concept name, so its 95.15% accuracy is compatible with learning concept/template-to-label associations and is not evidence by itself of general semantic principle recognition. These are source-derived weak-label metrics, not accuracy against independent human ground truth. Recovered-checkpoint test totals: 5,767 / 6,201 (93.00%) across 175 CINs. Source-wise metrics were recomputed from recovered seed-99 checkpoint `checkpoint-7460`; JSON: `results/audit/stage3_seed99_recovered_full_results.json`. The earlier report `results/audit/stage2_sourcewise_results.json` is retained as the pre-recovery result.

**P7 coverage limitation is explicit.** The concept coverage inventory found no P7-specific candidate among the unmapped Section C concepts. P7 has 543 samples in the rebuilt dataset from other sources; this does not prove Section C coverage for P7.

**Concept-disjoint Section C diagnostic (completed; technical checkpoint recovery verified):** 17 of 74 test-present Section C concepts were held out from supervised training and validation. The evaluation contains 1,190 rows from 174 CINs, with no company overlap between the underlying train/validation/test partitions. On these same held-out-concept rows, the full-concept baseline scored 1,166/1,190 Top-1 (97.98%; CIN-bootstrap 95% CI [97.15%, 98.76%]) and 1,183/1,190 Top-2 (99.41%). The one-seed concept-disjoint model scored 1,039/1,190 Top-1 (87.31%; CI [85.50%, 89.22%]) and 1,150/1,190 Top-2 (96.64%; macro-F1 0.6858). The paired Top-1 difference was −10.67 percentage points (CIN-bootstrap 95% CI [−12.36, −8.96]). P7 had no examples and P9 had only two, so classwise/macro-F1 interpretation is limited.

The first run emitted a checkpoint key mismatch: 50 BERT LayerNorm `gamma`/`beta` parameters were not loaded as `weight`/`bias`. The selected concept-disjoint checkpoint (step 6,270) and full-concept baseline checkpoint (step 7,460) were then recovered with exact key remapping, strict state-dict loading, and tensor-by-tensor save/reload verification; both passed. Re-evaluation produced the same point estimates as the original run. The paired comparison is therefore technically verified for these checkpoints, but it reuses the already-observed 1,190-row holdout and is **not a fresh test**. Results are still agreement with taxonomy-derived weak labels, not human-ground-truth semantic accuracy. Detailed recovered report: `results/audit/stage2_concept_disjoint_recovered_results.json`; recovery script: `results/audit/stage2_recover_layernorm_and_eval.py`.

**Three-holdout concept-disjoint stability run (completed):** Seeds 42, 17, and 73 evaluated 1,190, 1,167, and 1,169 held-out Section C rows respectively. Seed 42 reused its recovered checkpoint; seeds 17 and 73 were newly trained, with each validation-selected checkpoint strictly restored after remapping 50 LayerNorm aliases. Across the three hold-outs, concept-disjoint Top-1 was **81.64% ± 4.92 pp** (mean ± sample SD), Top-2 **95.34% ± 1.31 pp**, and macro-F1 **0.6752 ± 0.0170**. The full-concept baseline Top-1 averaged **97.07% ± 0.97 pp**; paired model-minus-baseline Top-1 difference averaged **−15.43 pp ± 4.22 pp**. This SD describes variability across these three hold-out/training runs, not a confidence interval or independent-test uncertainty: all runs reuse companies and rows from the same company-disjoint test partition, and seed 42 was already observed. Full per-run details: `results/audit/stage2_concept_disjoint_repeats_results.json`.

**Exploratory multi-label retraining (completed; existing test reused):** The user-run experiment grouped labels by company plus cleaned narrative, unioning all observed principle tags for a group. This produced 40,643 unique company-text groups, of which 2,644 had multiple labels; 37,999 groups had one label, and most multi-label groups had 8 or 9 labels. The company-disjoint partitions contained 28,590 train, 6,119 validation, and 5,934 test groups from 814/175/175 CINs, with zero CIN overlap. At fixed sigmoid threshold 0.5, the multi-label model achieved Hit@1 93.36% (5,540/5,934; CIN-bootstrap 95% CI [92.54%, 94.11%]), Hit@2 97.39% (5,779/5,934; [96.77%, 97.92%]), micro-F1 0.8898 ([0.8743, 0.9035]), macro-F1 0.8782 ([0.8606, 0.8942]), and exact-set match 90.26%. Its per-principle F1 ranged from 0.798 (P7) to 0.924 (P1/P3). On the same grouped labels and rows, the recovered single-label seed-99 baseline scored Hit@1 93.55%, Hit@2 97.81%, micro-F1 0.7490, macro-F1 0.6915, and exact-set match 87.14%. These metrics answer different questions: Hit@k checks whether a ranked prediction intersects the gold label set, while fixed-threshold F1/exact-set assess the predicted label set. The baseline emits only one label per row, so it has substantially lower multi-label recall; the multi-label model did not improve Hit@1/Hit@2. Do not summarize this as an across-the-board accuracy gain.

The new target is exploratory and remains taxonomy-derived weak supervision, including AI-assisted concept mappings, with no independent human ground truth. Unioning all tags for repeated company-text groups may retain genuine cross-cutting disclosures but can also combine tags attached to reused boilerplate. Source subsets can overlap because one grouped text may aggregate labels from multiple sources; for example, the Section B subset averaged 5.02 gold labels per row, so its 80.27% Hit@1 and 81.74% micro-F1 must not be compared directly with the prior single-label Section B accuracy. Section C's test subset contained no P7 positives. This re-evaluation reuses the established company-disjoint test set; it is not a fresh external test. The training used fixed threshold 0.5 without test-threshold tuning, selected a checkpoint using validation macro-F1, and passed strict restoration of 50 LayerNorm aliases plus save/reload tensor verification. Full report: `results/audit/stage2_multilabel_results.json`; user-run script: `results/audit/stage2_multilabel_retrain_eval.py`.

## Impact on later stages

The user subsequently rebuilt the company-disjoint split from the 42,409-row corpus and re-evaluated the recovered seed-99 checkpoint on its complete 6,201-row held-out test. The output reproduced 93.00% Top-1, 97.68% Top-2, and macro-F1 0.9158. Stage 5's zero-shot comparator was also rerun on the same rows. These remain evaluations against weak labels and reuse the established test set; they are not a new independent test. Do not use pre-rebuild segment-split metrics as if they were results on the company-disjoint test.

## Reproducibility and provenance

- Mapping implementation: `scripts/03_bert_training/build_training_dataset.py`
- Per-concept decisions: `data/labeling_sheets/stage2_concept_review/ai_decisions.csv`
- Mapping rationale and SEBI references: `results/audit/stage2_ai_mapping_provenance.md`
- Coverage inventory script: `results/audit/stage2_concept_coverage.py`
- Source-wise accuracy + filter-funnel audit: `results/audit/stage2_sourcewise_audit.py` (run by user with `.venv-ml`; JSON at `results/audit/stage2_sourcewise_results.json`)
- User-run rebuild command: `& ".\.venv-ml\Scripts\python.exe" "scripts\03_bert_training\build_training_dataset.py"`

The audit reports model agreement with source-derived weak labels on a company-disjoint test set; it does not claim expert validation or semantic ground-truth accuracy. The completed concept-disjoint Section C diagnostic is defined in `results/audit/stage2_concept_disjoint_eval.py`; its original output is `results/audit/stage2_concept_disjoint_results.json`, and its checkpoint-recovered recheck is `results/audit/stage2_concept_disjoint_recovered_results.json`. It withholds 17 concepts, uses one seed, and evaluates 1,190 held-out-concept rows from 174 CINs. The recovered recheck confirms a 10.67 pp Top-1 decrease relative to the full-concept baseline, with the reuse-of-test caveat above.
