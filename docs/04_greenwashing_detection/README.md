# Phase 4: Greenwashing Detection (Hybrid Lexicon + Semantic + XGBoost)

## What this phase does

This phase builds a system that flags narrative disclosure segments as
"vague" or "unsubstantiated" — hedging/aspirational language not backed
by any quantified evidence. It has three layered components: (1) a
rule-based hedging-term lexicon combined with a KPI/numeric-entity
detector, (2) a semantic layer using sentence embeddings to catch
paraphrased hedging that doesn't match any literal lexicon phrase, and
(3) an XGBoost meta-classifier trained on engineered features from the
first two layers, built specifically as a comparison against the
hand-tuned rules. A separate, complementary module (`greenwashing.py`,
covered here since it's part of the same overall verification effort)
checks a distinct signal: whether a narrative claim of improvement
contradicts the company's own filed numeric trend.

Core files:

- `src/analysis/vagueness_lexicon.py` — hedging-term lexicon + KPI/
  numeric-entity regex patterns
- `src/analysis/vagueness_semantic.py` — sentence-transformer embedding
  similarity against curated vague/quantified reference pools
- `src/analysis/vagueness_combined.py` — combines both layers
- `src/analysis/greenwashing.py` — claim-vs-XBRL-number contradiction
  detector (distinct signal: checks a claim against the company's own
  regulatory-filed numbers, not against language patterns)
- `scripts/04_greenwashing_detection/build_xgboost_dataset.py` and
  `train_xgboost_meta_classifier.py` — the XGBoost comparison

## Why this approach (not alternatives)

**Why hybrid, not lexicon-only or semantic-only.** A pure lexicon
approach (matching a fixed dictionary of ~30 hedging phrases like
"strives to", "committed to") is fast and precise but blind to
paraphrasing — a sentence like "our organisation continues its journey
towards a better tomorrow" contains none of the literal phrases but is
just as vague. A pure semantic-embedding approach solves that but is
noisier and has no built-in notion of "does this text contain a real
number" — a semantic model can be fooled by tone alone. Combining both
was a deliberate design choice from the start, matching the intent of
the original project plan's stated hybrid architecture, but implemented
and validated independently here rather than assumed to work.

**Why the claim-vs-XBRL-number contradiction check (`greenwashing.py`)
is a genuinely stronger signal than a general "MNLI-style" text-vs-text
contradiction detector.** A common architecture pattern for this kind of
system checks whether one piece of text entails or contradicts another
piece of text (e.g. comparing this year's claim against last year's
claim, or against a general-purpose fact-checking model's judgment).
This project instead checks a narrative claim against the _same
company's own officially-filed, audited XBRL numeric disclosure_ — not
another piece of prose. This is a stronger form of evidence, because the
thing being compared against is a regulatory fact the company itself
filed, not a probabilistic judgment about what two sentences mean
relative to each other.

**Why XGBoost was tried as a third layer, and why the final system still
uses the hand-tuned rules.** The hand-tuned lexicon+semantic system was
built first and iteratively refined against real evidence (see Bug Fixes
Log). XGBoost was then trained on 5 engineered features (hedging
density, KPI presence, semantic similarity scores, word count) from the
same 80 human-labeled validation samples, using Leave-One-Out
Cross-Validation (the appropriate evaluation method for a sample this
small — every sample gets predicted exactly once by a model trained on
the other 79, avoiding the high variance a single train/test split would
have at n=80). Result: XGBoost achieved a higher AUC-ROC (0.764 vs
0.731) but a lower F1 (0.675 vs 0.732) than the hand-tuned rules. The
hand-tuned system was kept as the production Truth Auditor component,
with the XGBoost comparison reported as a validation of the manual
design choices (feature importance analysis confirmed semantic
similarity and KPI-presence were the two dominant signals — exactly
matching what the manual design already prioritized) rather than a
replacement.

## Key decisions and trade-offs

**Decision: human-validate on a real, independently-labeled sample
rather than relying only on qualitative spot-checks.** 80 real narrative
segments (30 in an initial batch, 50 in a follow-up batch after the
first batch's correlation looked weak for a related reason — see Phase 6) were labeled 1/0 by direct human judgment while reading only the raw
text, without seeing the model's prediction, specifically to avoid
anchoring bias. This gave a real, if disclosed-as-small-sample,
precision/recall/AUC-ROC evaluation — Precision=0.917, Recall=0.846,
F1=0.880, AUC-ROC=0.894 on the final validated system.

**Trade-off accepted: the semantic layer's sentence-aggregation rule
optimizes for overall F1, at the cost of two known false negatives.**
Described in detail in the bug log below — a stricter rule was tried,
fixed those two cases, but broke six others. The looser rule (higher
overall F1) was kept, and the two remaining known false negatives are
disclosed as a limitation rather than hidden.

## Real bugs found and fixed here

1. **Paragraph-level analysis let one generic opening sentence
   contaminate an otherwise well-evidenced paragraph.** Both the lexicon
   KPI-check and the semantic-similarity check were initially applied to
   whole paragraphs. Real cases found: a paragraph starting "We have
   taken various initiatives..." (generic-sounding) followed by specific,
   verifiable facts (named ISO certifications, named offices) was
   flagged vague because the semantic embedding of the _whole_ paragraph
   leaned toward the vague reference pool, even though later sentences
   were clearly specific. Fixed by splitting into sentences and scoring
   each independently — the same class of bug was independently found
   and fixed in the separate `greenwashing.py` claim-evidence matcher
   (a Scope-2 claim in one sentence was being incorrectly attributed to
   Scope 1 because both sentences shared a paragraph with a hedging
   phrase).

2. **An attempted stricter fix regressed overall performance — this was
   caught by re-running the same evaluation, not assumed to be an
   improvement.** After fixing the paragraph-contamination bug with a
   "most-specific-sentence" scoring rule, two remaining false negatives
   were found (paragraphs with genuinely vague content but no single
   "rescuing" specific sentence to disprove it). A stricter two-condition
   rule (flag if ANY sentence is vague AND NO sentence is specific) was
   implemented to fix those two cases. Re-running the full validation
   showed precision dropped from 0.846 to 0.619 (F1 0.846 → 0.765) — the
   stricter rule introduced 6 new false positives, because many
   multi-sentence paragraphs contain at least one generically-toned
   connector sentence that superficially resembles the vague reference
   pool without being genuine hedging. This fix was **reverted** back to
   the looser rule, and the two known false negatives were documented as
   an accepted limitation instead — a deliberate choice to trust the
   overall evaluation metric over a plausible-sounding local fix.

3. **An overly-broad KPI-detection regex pattern (`zero[\s-]`) matched
   phrases that are not actually quantified evidence.** Added to catch
   genuine quantified claims like "zero fatalities" and
   "zero-manufacturing-waste-to-landfill", the pattern also matched
   "net-zero emissions" (an aspirational _target_ phrase, arguably
   hedging in its own right) and "zero-tolerance" (a policy statement,
   not a measured outcome) — causing genuinely vague paragraphs to be
   incorrectly treated as having KPI-evidence. Confirmed directly by
   testing the regex against all four example phrases in isolation
   before and after the fix. Fixed by restricting the pattern to "zero"
   immediately followed by a specific measured-outcome noun (incidents,
   fatalities, injuries, waste, discharge, etc.), with an additional fix
   for an optional single modifier word (to correctly match
   "zero-manufacturing-waste-to-landfill", where "manufacturing" sits
   between "zero" and "waste").

4. **A stale-CSV-predictions bug made a genuine code fix look like it had
   no effect at all.** After fixing the KPI-pattern bug above, re-running
   the evaluation script produced byte-for-byte identical results to the
   pre-fix run — a red flag investigated immediately rather than assumed
   to mean the fix didn't work. Root cause: the evaluation script was
   reading a `model_flagged` column that had been written to the CSV at
   _sample export time_ (using whatever detector code existed then),
   rather than re-running the current detector on the text live. Fixed
   by having the evaluation script always recompute predictions fresh
   from the current code on every run, never trusting a cached column.

## Your personal reflection (fill this in yourself)

_[This section is intentionally left for you to write in your own words.
Some starting questions to reflect on, based on the actual decisions
above:]_

- Bug #2 (the reverted two-condition rule) is a case where a fix that
  solved specific known problems still made the system worse overall.
  Have you encountered a similar trade-off in any other part of the
  project, or in your own past coding experience — a "correct-looking"
  fix that didn't actually help?
- The XGBoost comparison showed rule-based F1 beating XGBoost F1, but
  XGBoost winning on AUC-ROC. If you had to explain in one sentence which
  system is "better" to someone non-technical, what would you say, and
  why is that framing honest rather than picking whichever number looks
  more impressive?
- Why do you think the claim-vs-XBRL-number contradiction check
  (`greenwashing.py`) is described as "stronger evidence" than a
  general text-vs-text contradiction model? Do you agree with that
  framing, and can you explain it in your own words for a viva question?
