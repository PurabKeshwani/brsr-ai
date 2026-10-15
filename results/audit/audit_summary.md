# BRSR-AI GRASP — Master Audit Summary

**Git HEAD**: `be9fdb9f6cbba33ca99729e3fcd61e76a37b7dc6`  
**Audit generated**: 2026-10-15  
**Global rules applied**: No synthetic labels, no post-hoc cherry-picking, no exclusions without pre-stated criterion, every number gets N + CI.

---

## Master Results Table

| Stage | Metric | Old Value | New Value | Split Type | Label Source | N | 95% CI | Script Path | Status |
|---|---|---|---|---|---|---|---|---|---|
| S3 | Top-1 Accuracy | 93.83% | 93.13% | Segment-split (exact-dedup) | XBRL taxonomy | 5,197 | — | `scratch/audit_stage3_non_overlapping.py` | ✅ Done |
| S3 | Top-2 Accuracy | 98.07% | 97.73% | Segment-split (exact-dedup) | XBRL taxonomy | 5,197 | — | `scratch/audit_stage3_non_overlapping.py` | ✅ Done |
| S3 | Top-1 Accuracy | 93.83% | **PENDING** | **Company-disjoint** (0% overlap) | XBRL taxonomy | 5,721 | PENDING | `results/audit/task2_company_level_retrain.py` | 🔄 Retrain needed |
| S3 | Top-2 Accuracy | 98.07% | **PENDING** | Company-disjoint | XBRL taxonomy | 5,721 | PENDING | `results/audit/task2_company_level_retrain.py` | 🔄 Retrain needed |
| S3 | Macro-F1 | — | **PENDING** | Company-disjoint | XBRL taxonomy | 5,721 | PENDING | `results/audit/task2_company_level_retrain.py` | 🔄 Retrain needed |
| S3 | Top-1 (TF-IDF sim<0.90) | — | **93.15%** | Segment-split, near-dup filtered | XBRL taxonomy | 4,965 | — | `results/audit/task1_leakage_audit.py` | ✅ Done |
| S3 | Top-1 (TF-IDF sim>0.95 bucket) | — | **95.69%** | Near-verbatim duplicates | XBRL taxonomy | 812 | — | `results/audit/task1_leakage_audit.py` | ✅ Done (expected high) |
| S3 | Top-1 (TF-IDF sim 0.90-0.95) | — | **82.89%** | Near-dup zone | XBRL taxonomy | 76 | — | `results/audit/task1_leakage_audit.py` | ✅ Done |
| S4 | F1 (dev set) | 0.880 | **0.923** | Development set (N=80) | Human, blind labeling (batch 1+2) | 80 | — | `scripts/04_greenwashing_detection/evaluate_vagueness_detector.py` | ⚠️ Dev-set only |
| S4 | F1 (held-out) | — | **BLOCKED** | Held-out (batch 3, N=70) | Human labeling needed | 70 | BLOCKED | `results/audit/task4_batch3_eval.py` | ❌ BLOCKED: needs human |
| S5 | Top-1 Alignment | 44.3% | **PENDING** | Company-disjoint (post Task 2) | XBRL-BRSR taxonomy | — | PENDING | — | 🔄 Depends on Task 2 |
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

### Dataset Inventory

| File | Rows | MD5 (12) | Label Source | Status |
|---|---|---|---|---|
| `data/training/train.csv` | 27,272 | `d82f9533a5ed` | XBRL taxonomy (PrincipleAxis + concept mapping) | ✅ Active |
| `data/training/val.csv` | 5,841 | `620977ca06b2` | XBRL taxonomy | ✅ Active |
| `data/training/test.csv` | 5,853 | `af6efbec8ac8` | XBRL taxonomy | ✅ Active (company overlap!) |
| `data/training_company_split/train.csv` | 27,422 | `fb0e54c6bb93` | XBRL taxonomy, company-disjoint | ✅ Active |
| `data/training_company_split/val.csv` | 5,823 | `e76c077af370` | XBRL taxonomy, company-disjoint | ✅ Active |
| `data/training_company_split/test.csv` | 5,721 | `89201b663012` | XBRL taxonomy, company-disjoint | ✅ Active |
| `data/validation/human_score_validation.csv` | 20 | `b4bcf1feb232` | **Real human ratings** | ✅ Active |
| `data/validation/vagueness_validation_sample.csv` | 30 | `1962ea72c41b` | **Human, blind (batch 1)** | ✅ Dev set |
| `data/validation/vagueness_validation_sample_batch2.csv` | 50 | `9d3e8b99c815` | **Human, blind (batch 2)** | ✅ Dev set |
| `data/validation/vagueness_validation_sample_batch3.csv` | 70 | `9eb49f1d5848` | **BLOCKED: unlabeled** | ❌ Needs human |
| `data/validation/human_score_validation_n50.csv` | 50 | `20dc2f9e6db9` | **SYNTHETIC** (30/50 formula-generated) | ❌ Quarantined |
| `data/validation/lti_calibration_results_n50.csv` | 50 | `397525ad5f7e` | **SYNTHETIC** (derived from n50) | ❌ Quarantined |

### Source Breakdown (38,966 total)

| Source | Count | % | Label Rule |
|---|---|---|---|
| section_c | 33,022 | 84.7% | Concept name → principle (44-entry dict, SEBI BRSR Annexure I) |
| notes_principle | 3,417 | 8.8% | `NotesPrinciple{N}ExplanatoryTextBlock` → label N-1 |
| section_b | 2,527 | 6.5% | `fact.dimensions["PrincipleAxis"]` XBRL dimension |

---

## TASK 1 — Stage 3 Leakage Audit Findings

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
- **Status**: 🔄 READY TO RUN (needs GPU time ~3-5 hours for 5 seeds)
- **Command**: `python results/audit/task2_company_level_retrain.py`
- **Output**: `results/audit/task2_company_retrain_results.json`, `results/audit/stage3_trials.csv`

**Config**: Domain-Adapted BERT, LR=2e-5, 5 epochs, class weights, batch=16 (4×4 accum), 5 seeds.  
**Test**: Evaluated ONCE on `data/training_company_split/test.csv` (N=5,721, 0% company overlap).  
**Reporting**: Mean±std across seeds, cluster-bootstrap 95% CI by CIN.

---

## TASK 3 — Stage 5 Alignment (Pending Task 2)

Stage 5 re-evaluation must use the Task 2 model (company-disjoint encoder). Not started.

---

## TASK 4 — Stage 4 Greenwashing

| Item | Status | Details |
|---|---|---|
| Dev-set F1 (N=80) | ✅ 0.923 | Batches 1+2 used iteratively for engine development — this is a DEVELOPMENT set result |
| Batch 3 export (70 segments) | ✅ Done | `data/validation/vagueness_validation_sample_batch3.csv` |
| Batch 3 clean labeling sheet | ✅ Done | `data/labeling_sheets/stage4_batch3_clean.csv` — no model flags visible |
| Batch 3 labeling | ❌ **BLOCKED: needs human** | Two independent raters required; compute Cohen's kappa |
| Original batch labeling confirmation | ⚠️ UNVERIFIABLE | `model_flagged` + `flag_source` columns present in export CSVs; whether raters saw them is unknown |

> [!WARNING]
> Batch 3 export (`vagueness_validation_sample_batch3.csv`) contains `model_flagged` and `flag_source` columns. If raters fill `human_label` while seeing these, it is anchoring bias. The clean sheet (`stage4_batch3_clean.csv`) has only `id`, `company_name`, `text`.

---

## TASK 5 — Stage 6 Transparency Score

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
| **Anchoring bias** | `ai_transparency_score` column in `human_score_validation.csv`; script warns rater, but unverifiable. **Needs team confirmation.** |
| **Zensar URL artifact** | 1/107 bare-URL facts for Zensar; original human summary may have included thin content. Fixed in current export code. Re-rating needed. |
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
| BLOCKED-3 | S6 new ratings | `data/labeling_sheets/stage6_new_ratings.csv` | 30 companies to rate; rater sees ONLY narrative text, NOT `transparency_score` |
| BLOCKED-4 | S3 Section C spot-check | `data/labeling_sheets/stage3_section_c_spot_check.csv` | Expert verifies 207-row sample of concept→principle mapping |
| BLOCKED-5 | S6 Zensar re-rating | Re-run export for Zensar with fixed code, then human re-rates | Fresh Zensar rating with corrected (URL-filtered) summary |

---

## Claims We CAN Make

1. **Stage 3**: 93.13% Top-1 on 5,197 non-overlapping (exact-text-dedup) test segments. Labels from XBRL taxonomy (SEBI BRSR).
2. **Stage 3**: Company-disjoint split built (0% overlap by CIN). Retrain pending — number will be added after TASK 2.
3. **Stage 4**: F1=0.923 on 80-segment **development set** (not held-out).
4. **Stage 6**: Pearson r=0.6314 (N=20, 95% CI [0.268, 0.852], p=0.0028) using real human ratings and SEBI heuristic weights.
5. **Stage 6**: Post-hoc sensitivity r=0.7847 (N=18, excluding Geojit on BFSI non-applicability criterion AND Zensar on extraction bug criterion).

## Claims We CANNOT Make

1. ❌ **93.83%** as out-of-sample company generalization — it is within-company-distribution.
2. ❌ **r=0.9482** (LTI calibrated) — synthetic labels, quarantined.
3. ❌ **F1=0.923 as held-out test result** — it is a development set number.
4. ❌ **"Completeness Fallacy" weights** (0.45 Sp, 0.36 Cl, 0.13 Comp) — learned from synthetic labels.
5. ❌ **Anchoring-free human ratings** — unverifiable from file contents.
6. ❌ Any number without reporting N and 95% CI.

---

## Next Steps (in priority order)

1. **[USER action needed]** Run `python results/audit/task2_company_level_retrain.py` (GPU, ~3-5 hours).
2. **[USER action needed]** Have team fill `data/labeling_sheets/stage4_batch3_clean.csv` (two raters, blind).
3. **[USER action needed]** Confirm batch 1+2 labeling method (were model flags visible?).
4. After Task 2: Re-run Stage 5 alignment with company-disjoint encoder.
5. After Batch 3 labels: Run `task4_batch3_eval.py` to get honest Stage 4 held-out F1.
6. Get Zensar re-rated with fixed export, add to N=20, recompute Stage 6.
7. **[USER action needed]** Recruit 30+ raters for `stage6_new_ratings.csv` (rater sees no AI score).
8. After all numbers locked: update paper `CAPSTONE_RESEARCH_PAPER_LATEST`.
