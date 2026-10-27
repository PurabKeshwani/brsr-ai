# Stage 5 Final Audit — Regulatory Alignment

**Audit date:** 2026-10-18  
**Status:** Company-disjoint comparison re-evaluated with the strictly recovered seed-99 checkpoint; weak-label, test-reuse, and method-comparison caveats remain.  
**Framing:** Supervised transfer classifier versus zero-shot embedding baseline.

## Executive summary

The original reported **74.55% Top-1 / 84.99% Top-2** on N=393 is not cleared for reporting. Code inspection showed that the legacy compliance mapper loaded `data/models/brsr_principle_classifier/final_model_unweighted_93.68`, not the company-disjoint Stage 3 seed-99 checkpoint. The reconstructed 393 eligible segments came from **52 contributing companies**, not 100. Of these, 258 rows/37 CINs overlap the Stage 3 train split, including 111 normalized exact-text matches; 84 rows/8 CINs overlap validation; 51 rows/7 CINs overlap test. The old validator used `LIMIT 100` without explicit company ordering, so the reconstruction's exact membership is also subject to that query-order caveat.

The corrected comparison evaluates the recovered Stage 3 seed-99 classifier and zero-shot MPNet definition-plus-anchor hybrid on the same Stage 3 company-disjoint test set (**N=6,201; 175 CINs**). Top-1 was **93.00%** (5,767/6,201; CIN-bootstrap 95% CI [92.04%, 93.89%]) for supervised transfer versus **67.63%** (4,194/6,201; [66.45%, 68.93%]) for zero-shot. Top-2 was 97.68% vs 83.34%. The paired CIN-bootstrap Top-1 difference was **+25.37 percentage points** (95% CI **[24.02, 26.71] pp**). These are Top-k principle-label classification results against existing weak labels; they do not prove legal or regulatory compliance.

## Legacy N=393 overlap audit

| Stage 3 split | Overlapping sample CINs | Reconstructed rows in overlapping CINs | Normalized exact text hashes in split |
|---|---:|---:|---:|
| Train | 37 | 258 | 111 |
| Validation | 8 | 84 | 28 |
| Test | 7 | 51 | 26 |

All 393 reconstructed rows are accounted for across the three disjoint company splits. The historical sample-size report said “100 companies”; in the reconstruction, 100 companies were selected for inspection, but only 52 contributed eligible rows. The Stage 3 split-level overlap is direct evidence that this sample is not an unseen-company sample. The legacy model path mismatch independently prevents attributing the historical result to the Stage 3 company-disjoint model.

Artifacts: [`stage5_original_393_overlap.json`](stage5_original_393_overlap.json), [`stage5_original_100_company_sample.csv`](../../data/validation/stage5_original_100_company_sample.csv).

## Company-disjoint test evaluation

The evaluation script verified zero CIN overlap among the Stage 3 train, validation, and test CSVs. Both methods were evaluated on the exact same Stage 3 test rows. Confidence intervals use 2,000 CIN-cluster bootstrap resamples (seed 4206); paired deltas resample the same CIN clusters for both methods.

| Method | Top-1 | 95% CIN-bootstrap CI | Top-2 | 95% CIN-bootstrap CI | Macro-F1 |
|---|---:|---:|---:|---:|---:|
| Zero-shot MPNet definition + anchor hybrid | 67.63% (4,194/6,201) | [66.45%, 68.93%] | 83.34% (5,168/6,201) | [82.31%, 84.38%] | 0.6405 |
| Recovered Stage 3 seed-99 supervised transfer classifier | 93.00% (5,767/6,201) | [92.04%, 93.89%] | 97.68% (6,057/6,201) | [97.10%, 98.21%] | 0.9158 |
| Paired difference (supervised − zero-shot) | **+25.37 pp** | **[+24.02, +26.71 pp]** | **+14.34 pp** | **[+13.34, +15.42 pp]** | — |

### Per-principle Top-1 on the company-disjoint test set

| Principle | Support | Zero-shot | Supervised transfer |
|---|---:|---:|---:|
| P1 | 773 | 68.95% | 94.31% |
| P2 | 808 | 55.45% | 88.37% |
| P3 | 1,715 | 71.14% | 96.44% |
| P4 | 469 | 90.83% | 94.88% |
| P5 | 449 | 64.14% | 85.08% |
| P6 | 823 | 70.35% | 93.56% |
| P7 | 69 | 56.52% | 85.51% |
| P8 | 368 | 46.20% | 92.12% |
| P9 | 727 | 67.54% | 92.85% |

The prior P4 result of 57.1% came from the legacy N=393 evaluation and is not comparable to this test-set result. On the current company-disjoint set, P4 Top-1 is 94.88% (n=469). P7 has only 69 examples and is less stable.

Detailed current output: [`stage5_company_disjoint_recovered_results.json`](stage5_company_disjoint_recovered_results.json). Evaluation script: [`stage3_stage5_recovered_full_eval.py`](stage3_stage5_recovered_full_eval.py). The older `stage5_company_disjoint_results.json` is retained as pre-recovery history. Runtime mapper now points to `data/models/brsr_company_split_classifier/seed_99/recovered_checkpoint_7460`. API route: `GET /companies/{name}/compliance-mapping`; user verified a successful runtime response on 2026-10-19 with method `recovered_seed99_supervised_classifier` and the recovered checkpoint path. The route output is not a new validation metric.

## Correct interpretation

Describe the result as **supervised transfer versus zero-shot embedding on a company-disjoint held-out test set**. The supervised model is a BRSR-label fine-tuned classifier; the zero-shot method ranks principle definitions and anchors. This comparison shows the performance difference between these methods on the same examples, not an isolated causal effect of domain adaptation or alignment scoring.

The Stage 3 test split is reused here because it is the proper unseen-company split for this trained classifier. The split remains held out from training, but this is not an independent second test cohort beyond the Stage 3 evaluation.

## Limitations

1. **Checkpoint fidelity:** selected checkpoint-7460 was recovered by remapping 50 LayerNorm `gamma/beta` keys to `weight/bias`, strict loading, and exact tensor comparison after save/reload. The complete test was re-evaluated from that recovered checkpoint. Older best_model-based metrics are superseded.
2. **Weak-label target:** Stage 3 labels derive from the existing BRSR/XBRL mapping process, including AI-generated mappings not independently expert-validated. Accuracy is agreement with those labels, not independent expert correctness.
3. **Small P7 support:** P7 has 69 test segments.
4. **Different task formulations:** zero-shot similarity ranking and supervised classification are distinct methods; avoid claiming that alignment scoring alone improved by 25.35 pp.
5. **Regulatory scope:** a correct principle classification does not establish compliance with the principle's detailed requirements.
6. **Test reuse:** this repeats the established Stage 3 test evaluation after checkpoint repair; it is not an independent second test cohort.
7. **Legacy result:** 74.55%/84.99% on N=393 remains unverified against the Stage 3 model and is potentially affected by overlap; do not use it as the headline result.

## Reproducibility

- Stage 3 split: `data/training_company_split/{train,val,test}.csv`
- Selected checkpoint: `data/models/brsr_company_split_classifier/seed_99/checkpoints/checkpoint-7460`
- Recovered classifier: `data/models/brsr_company_split_classifier/seed_99/recovered_checkpoint_7460`
- Runtime model path: `src/analysis/compliance/compliance_mapper.py`
- Overlap audit script: `results/audit/stage5_overlap_audit.py`
- Recovered full-test evaluation script: `results/audit/stage3_stage5_recovered_full_eval.py`
- Recovered raw results: `results/audit/stage5_company_disjoint_recovered_results.json`
