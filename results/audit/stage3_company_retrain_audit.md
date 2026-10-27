# Stage 3 Final Run Audit — Company-Disjoint Classifier

**Run date:** 2026-10-18  
**Status:** Seed-99 checkpoint fidelity verified and full company-disjoint test re-evaluation completed. Metrics are reproducible for the recovered checkpoint; weak-label and test-reuse caveats remain.

## Split verification

The user rebuilt the company-level split from the current Stage 2 dataset and ran the five-seed retraining script.

| Split | Companies (CINs) | Rows |
|---|---:|---:|
| Train | 814 | 29,834 |
| Validation | 175 | 6,374 |
| Test | 175 | 6,201 |

All pairwise CIN overlap checks from the split-builder output were zero. There were 50 exact text matches between train and test across different companies (0.81% of test rows); this is cross-company boilerplate overlap, not company overlap.

## Training run

- Model: local domain-adapted BERT checkpoint.
- Hardware: NVIDIA GeForce RTX 2050, 4.3 GB VRAM.
- Five seeds completed: 42, 1, 7, 99, 2024.
- Five epochs per seed; validation macro-F1 mean 0.9175, standard deviation 0.0025.
- Best seed selected on validation macro-F1: seed 99 (0.9195).
- Test set: 6,201 examples, used for final model evaluation after seed selection.

## Test results

| Metric | Result | 95% CIN-cluster bootstrap CI |
|---|---:|---:|
| Top-1 accuracy | 93.00% (5,767/6,201) | [92.04%, 93.89%] |
| Top-2 accuracy | 97.68% (6,057/6,201) | [97.10%, 98.21%] |
| Macro-F1 | 0.9158 | [0.9036, 0.9277] |

Per-principle test support and F1:

| Principle | Support | F1 |
|---|---:|---:|
| P1 | 773 | 0.9511 |
| P2 | 808 | 0.8992 |
| P3 | 1,715 | 0.9588 |
| P4 | 469 | 0.9549 |
| P5 | 449 | 0.8751 |
| P6 | 823 | 0.9145 |
| P7 | 69 | 0.8551 |
| P8 | 368 | 0.9064 |
| P9 | 727 | 0.9272 |

## Audit caveats

1. **Checkpoint restoration:** the selected seed-99 checkpoint is `checkpoint-7460`. Its 50 LayerNorm `gamma/beta` keys were remapped to `weight/bias`, loaded strictly, saved, then reloaded and verified tensor-for-tensor. The full 6,201-row test was re-evaluated with this recovered model. The old `best_model`-based outputs are superseded by the recovered report.
2. **Weak-label ceiling:** the Stage 2 training labels include AI-generated concept mappings without independent expert validation. These test metrics measure agreement with the current weak-label pipeline on unseen companies; they do not establish independent semantic correctness of those labels.
3. **Residual boilerplate:** 50/6,201 test texts exactly matched a train text across different companies. Company leakage is zero by CIN, but these examples are not text-novel.
4. **Small P7 support:** P7 has 69 test examples, so its per-class F1 is less stable than classes with more support.
5. **Run revision metadata:** `task2_company_retrain_results.json` records a hard-coded historical Git hash (`be9fdb9...`), not a verified hash for the code/data state used in this run. Do not use that field as the run's exact code revision.
6. **Unsupervised corpus exposure:** `build_mlm_corpus.py` reads narratives across all companies, and `domain_pretrain_bert.py` uses that corpus. The exact membership used to produce the legacy encoder checkpoint is unverified. The zero CIN-overlap assertion establishes supervised split separation, not absence of validation/test-company exposure during MLM pretraining. New runs must record the encoder training corpus explicitly.

## Reproducibility files

- Raw metrics: `results/audit/task2_company_retrain_results.json`
- Recovered seed-99 full-test metrics: `results/audit/stage3_seed99_recovered_full_results.json`
- Recovery/re-evaluation: `results/audit/stage2_recover_layernorm_and_eval.py`, `results/audit/stage3_stage5_recovered_full_eval.py`
- Five-seed trials: `results/audit/stage3_trials.csv`
- Captured script log: `results/audit/task2_company_retrain_log.txt`
- Training and evaluation script: `results/audit/task2_company_level_retrain.py`
- Company-disjoint split builder: `scripts/03_bert_training/build_company_level_dataset.py`

## Verdict

The recovered seed-99 model scores 93.00% Top-1, 97.68% Top-2, and 0.9158 macro-F1 on the existing 6,201-row company-disjoint test. Its checkpoint load was verified. Report agreement with current taxonomy-derived weak labels, not independent semantic ground truth; this was a re-evaluation of the established test set, not a new test cohort.
