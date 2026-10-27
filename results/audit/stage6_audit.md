# Stage 6 Audit — Transparency Score

**Status:** Existing N=20 correlation audit complete; 30 new summaries and corrected Zensar have AI annotations only. Human validation remains unavailable.  
**Fixed score formula:** TS = 0.40 × Completeness + 0.30 × Specificity + 0.20 × Clarity + 0.10 × SDG alignment (SEBI heuristic weights).

## Current real-human-rating result

| Cohort | N | Pearson r (95% CI) | Spearman ρ (95% CI) | Pearson p | Interpretation |
|---|---:|---:|---:|---:|---|
| Full current cohort | 20 | 0.6314 [0.2683, 0.8519] | 0.6285 [0.2321, 0.8540] | 0.0028 | Current fixed-formula headline; small sample and blinding unconfirmed |
| Ex-Zensar | 19 | 0.7379 [0.5158, 0.8861] | 0.7432 [0.4555, 0.8921] | 0.0003 | Post-hoc sensitivity only; do not make headline |
| Ex-Zensar and Geojit | 18 | 0.7847 [0.5667, 0.9090] | 0.7615 [0.4250, 0.9144] | 0.0001 | Post-hoc sensitivity only; do not make headline |

Headline R² is 0.3986; MAE is 12.16 and RMSE is 15.19. The observed score range is 26.9–75.6, and peer normalization covers 47 sectors. These are descriptive properties of the current analysis, not evidence of broad generalizability.

## Provenance and validity issues

1. **Anchoring risk:** `data/validation/human_score_validation.csv` has `ai_transparency_score` next to `human_score`. Whether the rater saw the model score is unconfirmed. The current N=20 result is real human-rated data but cannot be described as confirmed blind or anchoring-free.
2. **New-rating file is not safe to share:** `data/labeling_sheets/stage6_new_ratings.csv` contains `transparency_score` and `human_score` in the same file. It is a private score-bearing key, not a rater sheet. The human-rater export script explicitly warns to strip the score, but relies on manual handling.
3. **Zensar rating artifact:** the original narrative packet included URL-heavy policy links due to the earlier selection/export bug. The existing Zensar human score should be replaced with a fresh blind rating from a corrected, URL-stripped narrative packet; do not count it as an additional company.
4. **Small sample and rater source:** N=20 produces wide confidence intervals. The ratings come from a single rater source; no inter-rater reliability is available. Geojit is a BFSI broker whose business is a sector mismatch for manufacturing-oriented indicators; document this without excluding it from the headline cohort.
5. **Post-hoc exclusions:** N=19 and N=18 cohorts are sensitivities chosen after inspecting results/residuals. They are not headline estimates.

## Invalid or exploratory results

- **Quarantined synthetic N=50:** 48/50 labels were formula-generated. LTI Pearson r=0.9482 and Spearman ρ=0.993 are invalid and must not appear in the paper or presentation.
- **“Completeness Fallacy” weights:** the 0.45 Specificity / 0.36 Clarity / 0.13 Completeness weights derive from synthetic data and must not be reported.
- **LOOCV weight calibration:** r=0.4993 on N=20 is exploratory only and unstable at this sample size.
- **Old 5-fold result:** r=0.7128 has inconsistent N provenance and must not be reported.

## Next validation design

The score-weighted candidate list and existing `stage6_new_ratings.csv` stay private. A new exporter creates blind rating sheets without model scores, plus stripped narrative summaries, for 30 new companies and a separate corrected Zensar rerating. Only the blind sheets, narratives, and instructions are for the human rater.

When ratings return:

1. Validate 30 new scores are present and within 0–100; replace Zensar's existing human rating rather than adding a 21st historic company.
2. Preserve the 20-company historic cohort as calibration data and evaluate the frozen SEBI formula on the 30 newly blind-rated companies. Any weight calibration must use only the designated calibration split and must not use the 30-company evaluation split. Report the fixed SEBI formula as the primary result and calibrated weights separately as exploratory.
3. Report evaluation N, Pearson/Spearman confidence intervals, rater provenance, the N=20 blinding uncertainty, small-sample limitation, single-rater-source limitation, and Geojit sector mismatch.

This plan produces a 30-company blind evaluation. Do not describe a combined correlation over all 50 as held-out if the 20 historic ratings were used for calibration or their blinding remains uncertain.

## AI annotation outcome (exploratory only)

Because no human raters were available, an AI language model scored the 30 score-free company summaries and the corrected Zensar summary using the 0–100 anchors above. The separate artifact is `data/labeling_sheets/stage6_ai_annotations.csv`; annotation method and limitations are documented in `data/labeling_sheets/stage6_ai_annotations_provenance.md`.

These 31 scores are **AI-generated narrative assessments**, not human ratings, not independent ground truth, and not a replacement for the N=50 real-human validation plan. They do not provide inter-rater reliability or Cohen's kappa. Do not merge them into the human-score file, use them to claim a real-human N=50, or describe a correlation against the algorithmic scores as independent validation. The corrected Zensar AI score is exploratory and does not replace the historical human score in the N=20 audit.

## Reproducibility and handoff

- Existing metrics and provenance: `results/audit/task5_stage6_results.json`, `results/audit/task5_stage6_log.txt`
- Current formula: `src/analysis/scoring/transparency_score.py`
- Blind packet exporter: `scripts/06_transparency_score/export_stage6_blind_rater_packets.py`
- Existing score-bearing private sheet: `data/labeling_sheets/stage6_new_ratings.csv` — do not give to raters.
- Expected rater-facing files after exporter runs: `data/labeling_sheets/stage6_new_ratings_blind.csv`, `stage6_new_ratings_summaries.txt`, `stage6_zensar_rerating_blind.csv`, `stage6_zensar_rerating_summaries.txt`, and `stage6_blind_rater_instructions.md`.
- AI-only annotations (not human ratings): `data/labeling_sheets/stage6_ai_annotations.csv` and `data/labeling_sheets/stage6_ai_annotations_provenance.md`.
- Quarantined invalid files: `data/quarantine/human_score_validation_n50.csv`, `data/quarantine/lti_calibration_results_n50.csv`.
