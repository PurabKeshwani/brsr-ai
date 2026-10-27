# Phase 0 audit review

Completed on 2026-10-19. Document preparation, saved-result import, runtime metadata capture, and frozen-split verification: **PASS** in [phase0_setup.json](phase0_setup.json). Training/inference/new performance estimates: **NOT RUN**.

The user ran the setup with `D:\brsr-ai-phase0-1\brsr-ai\.venv-ml\Scripts\python.exe` (Python 3.13.14). It recorded Git commit `94fafa1bbdaf1c4801e2559136d18ec5c482d823` with a dirty worktree and tracked-diff SHA-256 `a148d488f3114dddfda8968fa53aa59a4a7988f7583e14c6c8a709984e930226`. CUDA is available on an NVIDIA GeForce RTX 2050 (4,294,443,008 bytes). Imported result hashes all matched their source files.

Frozen company split metadata: train 29,834 rows / 814 CINs, validation 6,374 / 175, test 6,201 / 175. All three pairwise CIN overlaps are zero. The test CSV SHA-256 is `079305b42510bed095c9bd937380a483951a76fbca42fb4ac10b55b4d829391d`, matching the preregistered historical test reference. This was metadata/CIN inspection only; no model, labels, or test performance were evaluated. The exact lifetime count of earlier test evaluations remains unknown.

All baseline values below are imported historical user-run audit results, preserved with original source paths and SHA-256 hashes in [baseline_snapshot.json](baseline_snapshot.json). They were not rerun. Machine-readable table rows, source selectors, and findings are in [audit_review.json](audit_review.json). Missing intervals are not fabricated.

## Baseline inventory

| Stage | Metric | Historical estimate | N | Existing 95% CI / missingness | Allowed interpretation |
|---|---|---|---|---|---|
| 2 | section_b Top-1 | 63.35% | 352 | [56.55%, 69.67%] | historical weak-label agreement |
| 2 | section_c Top-1 | 95.15% | 5364 | [94.41%, 95.92%] | historical weak-label agreement |
| 2 | notes_principle Top-1 | 90.72% | 485 | [86.55%, 94.09%] | historical weak-label agreement |
| 3 | Top-1 | 93.00% | 6201 | [92.04%, 93.89%] | historical weak-label agreement; existing test reused |
| 3 | Top-2 | 97.68% | 6201 | [97.10%, 98.21%] | historical weak-label agreement; existing test reused |
| 3 | macro-F1 | 0.9158 | 6201 | [0.9036, 0.9277] | historical weak-label agreement; existing test reused |
| 3 diagnostic | concept-disjoint Top-1 mean | 81.64% ± 4.92 pp SD | 1190 / 1167 / 1169 | No CI of cross-holdout mean; sample SD is not a CI | historical repeated concept holdout; existing test reused |
| 4 | F1 | 0.7436 | 80 | NOT COMPUTED in the existing source | human-development only; blinding unconfirmed |
| 4 AI comparison | F1 | 0.6885 | 70 | NOT COMPUTED in the existing source | historical AI-label comparison only; excluded from tuning and headline claims |
| 5 | zero-shot Top-1 | 67.63% | 6201 | [66.45%, 68.93%] | historical method comparison on weak labels |
| 5 | paired supervised minus zero-shot Top-1 | +25.37 pp | 6201 | [+24.02, +26.71] pp | historical paired comparison; not causal compliance gain |
| 6 | Pearson r | 0.6314 | 20 | [0.2683, 0.8519] | historical human ratings; blinding unconfirmed |
| 6 | Spearman rho | 0.6285 | 20 | [0.2321, 0.8540] | historical human ratings; blinding unconfirmed |

CIN counts and full metric/support details are in the JSONs. Stage 5 supervised metrics reuse the Stage 3 model/test, not another independent performance sample. Cross-holdout SD is not a confidence interval. The historical AI-label row is descriptive context only and is excluded from improvement tuning and headline validation.

## Findings and actions

- **MLM data scope needs correction for new runs.** The corpus builder queries all-company narrative facts; exact legacy-checkpoint corpus membership remains unresolved. The user selected train-company-only MLM adaptation for new candidates. This is a Phase 1 prerequisite, not a completed training run. See F01 in audit_review.json.
- **Frozen does not mean fresh.** Test outcomes are already known from prior audits. New configurations get one prospective test evaluation; historical counts/timestamps remain unknown. The log does not erase that exposure.
- **Paired before/after CIs need paired rows.** No filename-matched prediction caches were located in the bounded search. Recover the original cache or explicitly amend the protocol before rerunning an old comparator; aggregate summaries cannot provide paired CIs.
- **Filing-consistency indicators need a defined reference.** A zero value is an observation. Absence may mean non-applicability or unresolved matching. Freeze claim/fact/year/unit/boundary linking and report proxy consistency; do not call this greenwashing ground truth or compare a rule with itself.
- **Transparency proxies can be circular.** Numeric presence is related to specificity construction. Report construct/internal-consistency evidence and overlap sensitivities; no new human-validation claim follows from proxy correlation or rank stability. The local code attributes the weight formula to the project report; SEBI-prescribed weighting remains unverified.
- **Recovered JSON takes precedence over stale prose.** Notes CI and affected per-principle values were corrected in current audit docs; the Stage 5 detail link now points to its recovered JSON. All corrections use saved results, not new evaluation. See F06 in audit_review.json.

The improvement protocol is [prereg.md](prereg.md). Label provenance for principle tasks remains **agreement with taxonomy-derived weak labels (partly AI-assisted mapping)**. Human development labels and historic human ratings retain their separate provenance and blinding caveats.

## Claims excluded from paper headlines

Do not report these as final validated results: 93.83%, 98.07%, 0.9341, 96.66% calibration, 98–99% sliding-window results, legacy Stage 5 74.55%/84.99%, Stage 4 F1 0.923 or in-sample F1 1.000, Stage 6 r=0.9482, “Completeness Fallacy” weights, historical Section B count 17,219, or the unachieved XGBoost F1 target 0.94–0.96. They are stale, compromised, in-sample, synthetic, or otherwise unsupported for the paper claims.

This exclusion list is historical bookkeeping, not experiment output. Do not open quarantined data, train/tune on AI annotations, or edit the paper in this study.

## Phase 0 completion

[phase0_setup.json](phase0_setup.json) reports PASS with no errors. The test access ledger records this as metadata-only access. An earlier setup attempt remains listed as RUNNING in the experiment ledger without a result record; its outcome is unknown, so its entry is retained. Phase 1 training has not run. Stop here as required by the phase-by-phase protocol.
