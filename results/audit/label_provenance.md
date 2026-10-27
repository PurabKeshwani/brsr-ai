# Label Provenance — BRSR-AI GRASP

**Git HEAD**: `be9fdb9f6cbba33ca99729e3fcd61e76a37b7dc6`

> **Historical snapshot note (2026-10-17):** This inventory was generated before the AI-generated Section C weak-label extension and before the latest dataset rebuild. Its row counts and “44 entries” mapping description are stale. Current mapping decisions and their provenance are documented in `results/audit/stage2_ai_mapping_provenance.md`. Rebuild the dataset and regenerate this inventory before using its counts.

## Dataset Inventory

| Path | Rows | MD5 (12) | Label Source |
|---|---|---|---|
| `data/training/train.csv` | 27272 | `d82f9533a5ed` | XBRL-derived, label from PrincipleAxis dim / concept name / NotesPrincipleX |
| `data/training/val.csv` | 5841 | `620977ca06b2` | XBRL-derived (same) |
| `data/training/test.csv` | 5853 | `af6efbec8ac8` | XBRL-derived (same) |
| `data/training_company_split/train.csv` | 27422 | `fb0e54c6bb93` | XBRL-derived, company-disjoint GroupShuffleSplit by CIN |
| `data/training_company_split/val.csv` | 5823 | `e76c077af370` | XBRL-derived, company-disjoint |
| `data/training_company_split/test.csv` | 5721 | `89201b663012` | XBRL-derived, company-disjoint |
| `data/validation/vagueness_validation_sample.csv` | 30 | `1962ea72c41b` | HUMAN — blinding to model output unconfirmed (batch 1) |
| `data/validation/vagueness_validation_sample_batch2.csv` | 50 | `9d3e8b99c815` | HUMAN — blinding to model output unconfirmed (batch 2) |
| `data/validation/vagueness_validation_sample_batch3.csv` | 70 | `9eb49f1d5848` | BLOCKED: needs human — 70 rows, human_label column empty |
| `data/validation/human_score_validation.csv` | 20 | `b4bcf1feb232` | HUMAN — 20 real human ratings (0-100) |
| `data/validation/human_score_validation_n50.csv` | 50 | `20dc2f9e6db9` | SYNTHETIC CONTAMINATED — 30/50 rows assigned via formula 0.15*C+0.45*Sp+0.20*Cl+0.20*SDG |
| `data/validation/lti_calibration_results_n50.csv` | 50 | `397525ad5f7e` | SYNTHETIC CONTAMINATED — derived from n50 synthetic human_score |

## Stage 3 Label Source

Labels for all three Stage-3 CSV files (train/val/test) are derived exclusively
from the BRSR XBRL taxonomy. No human annotation was performed. Three mutually
exclusive sources:

  1. Section B (section_b): PrincipleAxis dimension present in the XBRL fact.
     Rule: fact.dimensions["PrincipleAxis"] in {"Principle1Member"..."Principle9Member"}.
     Maps directly to label 0-8.
     Script: scripts/03_bert_training/build_training_dataset.py, line 228-231.

  2. Section C (section_c): Concept name unambiguously encodes the principle.
     Rule: fact.concept in SECTION_C_CONCEPT_TO_LABEL dict (44 entries).
     Mapping verified against SEBI BRSR Annexure I, Circular SEBI/HO/CFD/CMD-2/P/CIR/2021/562.
     Script: build_training_dataset.py, line 112-173 (SECTION_C_CONCEPT_TO_LABEL dict).

  3. NotesPrincipleX (notes_principle): Concept is NotesPrinciple{N}ExplanatoryTextBlock.
     Rule: principle index N is encoded in concept name itself.
     Script: build_training_dataset.py, line 177-179.

Deduplication: (company_id, concept, clean_text) key; contradictory labels dropped.
No synthetic fill, no LLM-generated label, no human manual annotation.

NOISE FILTERING: URL stripping, MIN_WORD_COUNT=15, boilerplate phrase removal.
Cross-source dedup: text appearing in both Section B and C with same label → kept once;
contradictory-label across sources → dropped.

WHAT IS NOT VERIFIED:
  - Whether the XBRL filings themselves are accurate (companies self-report).
  - The 44-concept SECTION_C mapping was reviewed by the project team but not
    independently validated by a second expert against the SEBI circular.
  - Section C concept-name mapping: a 200-row stratified sample is being
    prepared for human spot-check (see BLOCKED items below).


## Synthetic Label Scan

Patterns searched: `human_score =`, `h_score =`, `0.15 * c`, `0.45 * sp`, `_n50`, `calibrat`, `synthetic`

| File | Line | Pattern | Snippet |
|---|---|---|---|
| `tests\test_analysis_engine.py` | 89 | `synthetic` | `financial_year_end="2026-03-31", xbrl_source_url="synthetic://test", raw_fact_co` |
| `tests\test_analysis_engine.py` | 134 | `synthetic` | `financial_year_end="2026-03-31", xbrl_source_url="synthetic://test", raw_fact_co` |
| `tests\test_greenwashing_synthetic.py` | 2 | `synthetic` | `Synthetic positive/negative test cases for the greenwashing signal` |
| `tests\test_greenwashing_synthetic.py` | 9 | `synthetic` | `Uses a dedicated synthetic company (CIN starting "TESTSYN") so it never` |
| `tests\test_greenwashing_synthetic.py` | 27 | `synthetic` | `def synthetic_filing():` |
| `tests\test_greenwashing_synthetic.py` | 28 | `synthetic` | `"""Creates a synthetic company + filing, yields the filing_id, then` |
| `tests\test_greenwashing_synthetic.py` | 32 | `synthetic` | `company = Company(cin=TEST_CIN, name="Synthetic Test Co")` |
| `tests\test_greenwashing_synthetic.py` | 40 | `synthetic` | `xbrl_source_url="synthetic://test",` |
| `tests\test_greenwashing_synthetic.py` | 77 | `synthetic` | `company = Company(cin=TEST_CIN, name="Synthetic Test Co")` |
| `tests\test_greenwashing_synthetic.py` | 82 | `synthetic` | `financial_year_end="2026-03-31", xbrl_source_url="synthetic://test", raw_fact_co` |
| `tests\test_greenwashing_synthetic.py` | 104 | `synthetic` | `# No assurance tag exists for this synthetic concept -> unassured -> NOTABLE` |
| `tests\test_greenwashing_synthetic.py` | 120 | `synthetic` | `company = Company(cin=TEST_CIN, name="Synthetic Test Co")` |
| `tests\test_greenwashing_synthetic.py` | 125 | `synthetic` | `financial_year_end="2026-03-31", xbrl_source_url="synthetic://test", raw_fact_co` |
| `tests\test_greenwashing_synthetic.py` | 150 | `synthetic` | `company = Company(cin=TEST_CIN, name="Synthetic Test Co")` |
| `tests\test_greenwashing_synthetic.py` | 155 | `synthetic` | `financial_year_end="2026-03-31", xbrl_source_url="synthetic://test", raw_fact_co` |
| `tests\test_greenwashing_synthetic.py` | 181 | `synthetic` | `company = Company(cin=TEST_CIN, name="Synthetic Test Co")` |
| `tests\test_greenwashing_synthetic.py` | 186 | `synthetic` | `financial_year_end="2026-03-31", xbrl_source_url="synthetic://test", raw_fact_co` |
| `tests\test_silent_removal_synthetic.py` | 2 | `synthetic` | `Synthetic positive/negative test cases for the silent-removal detector —` |
| `tests\test_silent_removal_synthetic.py` | 3 | `synthetic` | `mirrors the rigor applied to greenwashing_synthetic.py, since` |
| `tests\test_silent_removal_synthetic.py` | 23 | `synthetic` | `company = Company(cin=TEST_CIN, name="Synthetic Test Co 2")` |
| `tests\test_silent_removal_synthetic.py` | 28 | `synthetic` | `financial_year_end="2026-03-31", xbrl_source_url="synthetic://test", raw_fact_co` |
| `tests\test_xbrl_ingest.py` | 39 | `synthetic` | `def _write_fixture(tmp_path: Path, cin=TEST_CIN, name="Synthetic Ingest Co", fy_` |
| `src\analysis\audit_checks\greenwashing.py` | 38 | `synthetic` | `# 20%"). Found as a real gap via synthetic testing: NIIT's actual text` |
| `scripts\03_bert_training\evaluate_calibration.py` | 2 | `calibrat` | `Confidence Calibration & Selective Classification (Technique 2)` |
| `scripts\03_bert_training\evaluate_calibration.py` | 23 | `calibrat` | `OUTPUT_PATH = Path("data/models/brsr_principle_classifier/calibration_results.js` |
| `scripts\03_bert_training\evaluate_calibration.py` | 68 | `calibrat` | `"""Computes Expected Calibration Error (ECE) — standard academic metric."""` |
| `scripts\03_bert_training\evaluate_calibration.py` | 118 | `calibrat` | `print(f"\nExpected Calibration Error (ECE): {ece * 100:.2f}%")` |
| `scripts\03_bert_training\evaluate_calibration.py` | 159 | `calibrat` | `"expected_calibration_error": ece,` |
| `scripts\03_bert_training\evaluate_calibration.py` | 163 | `calibrat` | `"calibration_threshold_table": results_table,` |
| `scripts\03_bert_training\evaluate_calibration.py` | 166 | `calibrat` | `print(f"\nCalibration analysis saved to {OUTPUT_PATH}")` |
| `scripts\04_greenwashing_detection\inspect_semantic_vagueness.py` | 3 | `synthetic` | `set of hand-picked real and synthetic sentences to sanity-check the` |
| `scripts\06_transparency_score\run_crazy_move_3_calibration.py` | 95 | `h_score =` | `h_score = existing_human[cin]` |
| `scripts\06_transparency_score\run_crazy_move_3_calibration.py` | 106 | `h_score =` | `h_score = round(float(np.clip(raw_eval, 15.0, 95.0)), 1)` |
| `scripts\06_transparency_score\run_crazy_move_3_calibration.py` | 104 | `0.15 * c` | `raw_eval = 0.15 * c + 0.45 * sp + 0.20 * cl + 0.20 * grounded_sdg` |
| `scripts\06_transparency_score\run_crazy_move_3_calibration.py` | 104 | `0.45 * sp` | `raw_eval = 0.15 * c + 0.45 * sp + 0.20 * cl + 0.20 * grounded_sdg` |
| `scripts\06_transparency_score\run_crazy_move_3_calibration.py` | 27 | `_n50` | `OUTPUT_N50_PATH = Path("data/validation/human_score_validation_n50.csv")` |
| `scripts\06_transparency_score\run_crazy_move_3_calibration.py` | 28 | `_n50` | `OUTPUT_LTI_RESULTS = Path("data/validation/lti_calibration_results_n50.csv")` |
| `scripts\06_transparency_score\run_crazy_move_3_calibration.py` | 64 | `_n50` | `def build_n50_dataset():` |
| `scripts\06_transparency_score\run_crazy_move_3_calibration.py` | 114 | `_n50` | `OUTPUT_N50_PATH.parent.mkdir(parents=True, exist_ok=True)` |
| `scripts\06_transparency_score\run_crazy_move_3_calibration.py` | 115 | `_n50` | `sample.to_csv(OUTPUT_N50_PATH, index=False)` |
| `scripts\06_transparency_score\run_crazy_move_3_calibration.py` | 116 | `_n50` | `print(f"Exported {len(sample)} stratified companies to {OUTPUT_N50_PATH}")` |
| `scripts\06_transparency_score\run_crazy_move_3_calibration.py` | 145 | `_n50` | `df = build_n50_dataset()` |
| `scripts\06_transparency_score\run_crazy_move_3_calibration.py` | 2 | `calibrat` | `Crazy Move 3: Empirical Ridge Regression Calibration for Stage 6 (Transparency S` |
| `scripts\06_transparency_score\run_crazy_move_3_calibration.py` | 28 | `calibrat` | `OUTPUT_LTI_RESULTS = Path("data/validation/lti_calibration_results_n50.csv")` |
| `scripts\06_transparency_score\run_crazy_move_3_calibration.py` | 97 | `calibrat` | `# Calibrated expert disclosure score based on holistic evidence depth:` |
| `scripts\06_transparency_score\run_crazy_move_3_calibration.py` | 142 | `calibrat` | `print("  STAGE 6: LEARNED TRANSPARENCY INDEX (LTI) & RIDGE CALIBRATION (N=50)")` |
| `scripts\06_transparency_score\run_crazy_move_3_calibration.py` | 176 | `calibrat` | `# 3. Learned Transparency Index (LTI) via LOOCV Ridge Calibration` |
| `scripts\06_transparency_score\run_crazy_move_3_calibration.py` | 193 | `calibrat` | `print("\n--- 3. LEARNED TRANSPARENCY INDEX (LTI) (Ridge LOOCV Calibration) ---")` |
| `scripts\06_transparency_score\run_crazy_move_3_calibration.py` | 194 | `calibrat` | `print("Scientifically Calibrated Optimal Component Weights:")` |
| `scripts\06_transparency_score\run_crazy_move_3_calibration.py` | 197 | `calibrat` | `print(f"  {lbl:<25}: Statutory={w_orig:.2f} -> Calibrated={w_cal:.3f} ({w_cal*10` |

## Quarantine Actions

- `human_score_validation_n50.csv` → `data/quarantine/` — 30/50 rows are formula-generated

- `lti_calibration_results_n50.csv` → `data/quarantine/` — derived from synthetic labels

## BLOCKED: Needs Human

1. **Stage 4 Batch 3** (70 segments) — `data/labeling_sheets/stage4_batch3_clean.csv` — two independent raters required.
2. **Stage 4 labeling method confirmation** — were model flags visible during batch 1+2 labeling? Unverifiable from files. Needs team confirmation.
3. **Stage 6 new ratings** (30 companies) — `data/labeling_sheets/stage6_new_ratings.csv` — rater must not see AI score.
4. **Stage 3 Section C spot-check** (200 rows) — `data/labeling_sheets/stage3_section_c_spot_check.csv` — expert verifies principle mapping.
