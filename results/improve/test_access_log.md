# Test access ledger

This study begins after the existing test and concept-test subsets have already been evaluated. Exact historical run times and lifetime evaluation counts are unknown. Do not reset history to zero or call the cohort fresh.

Phase 0 imported existing audit JSON reports only. It did not run a model or read frozen dataset CSV contents during document preparation. Its user-run setup script will hash/check CSV CIN metadata, logged separately as METADATA_ONLY. This is not a test metric evaluation.

For new model evaluations, reserve an entry before inference containing config ID/hash, checkpoint hash, test hash, UTC timestamp, role, and exact result/cache file. Append completion/failure; do not delete failed or interrupted accesses. Compute all metrics/subsets/CIs from the same saved logits. A phase-specific inference guard must reject a repeated config evaluation before Phase 1 final testing is allowed.

Historical output references (imports, not new evaluations):

- `results/audit/stage3_seed99_recovered_full_results.json`
- `results/audit/stage5_company_disjoint_recovered_results.json`
- `results/audit/stage2_concept_disjoint_repeats_results.json`
- `results/audit/stage2_multilabel_results.json`

Imported records and source hashes: `results/improve/baseline_snapshot.json`.

| Config / event ID | UTC timestamp | Access type / status | Dataset | Result / cache file | Notes |
|---|---|---|---|---|---|
| P0-20261019T125107652794Z | 2026-10-19T12:51:30.782720+00:00 | METADATA_ONLY_STARTED | `data/training_company_split/test.csv` | `results/improve/phase0_setup.json` | Hash/CIN check only; no prediction |
| P0-20261019T125107652794Z | 2026-10-19T12:51:31.380595+00:00 | METADATA_ONLY_PASS | `data/training_company_split/test.csv` | `results/improve/phase0_setup.json` | No model/test evaluation performed |
| P1-MLM-AUDIT-20261019T130038766844Z | 2026-10-19T13:00:38.980592+00:00 | METADATA_ONLY_STARTED | `data/training_company_split/test.csv` | `results/improve/legacy_mlm_exposure.json` | CIN membership plus saved-corpus attribution; no labels/predictions |
| P1-MLM-AUDIT-20261019T130038766844Z | 2026-10-19T13:00:48.061931+00:00 | METADATA_ONLY_PASS | `data/training_company_split/test.csv` | `results/improve/legacy_mlm_exposure.json` | Corpus/DB attribution only; no test labels or metrics |
| P1-MLM-CORPUS-20261019T130814431775Z | 2026-10-19T13:08:14.623548+00:00 | METADATA_ONLY_STARTED | `data/training_company_split/test.csv` | `results/improve/train_only_mlm_corpus_manifest.json` | CIN and exact-text embargo check; no labels or model scores |
| P1-MLM-CORPUS-20261019T130814431775Z | 2026-10-19T13:08:20.411864+00:00 | METADATA_ONLY_PASS | `data/training_company_split/test.csv` | `results/improve/train_only_mlm_corpus_manifest.json` | Exact-text embargo verified; no model scores |
