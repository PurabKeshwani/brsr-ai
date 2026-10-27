# Legacy MLM corpus exposure audit

The user-run [audit result](legacy_mlm_exposure.json) passed on 2026-10-19. This was a corpus/DB attribution check only. Training, inference, validation scoring, and test performance evaluation were **NOT RUN**.

| Saved-corpus measure | Count |
|---|---:|
| Unique sentences in actual saved corpus | 50,894 |
| Sentences matched to current DB | 50,894 |
| Saved sentences unmatched in current DB | 0 |
| Current DB sentences absent from saved corpus | 25 |
| Associated with validation CINs | 7,750 |
| Associated with test CINs | 7,467 |
| Associated with validation or test CINs (union) | 15,178 / 50,894 (29.82%) |
| Validation/test-associated with no train-CIN match | 14,960 |
| Also associated with train CINs | 218 |
| Eligible saved sentences attributable only to train CINs | 35,716 |

The legacy corpus has no CIN column and was globally deduplicated. A sentence filed by multiple companies is counted in each contributing cohort, then counted once in the validation/test union. The old “51,066 sentences” description does not match the saved corpus inspected here; use the measured 50,894 when referring to this file. The current DB has 25 additional unique texts, so it is not an exact reconstruction of the saved corpus.

The source builder read all companies. The saved corpus is substantially associated with validation/test companies. The checkpoint config does not contain a corpus hash, so its exact historical training input remains unproven. Under the [preregistered rule](prereg.md), the new Stage 3 base will be trained on the saved-corpus subset attributable exclusively to train CINs. The verdict is **leakage control**, regardless of later validation accuracy. Shared exact text is embargoed. The controlled old/new comparison uses identical validation rows and a matched supervised recipe; historical old test metrics and the one prospective new final test evaluation are labeled separately.
