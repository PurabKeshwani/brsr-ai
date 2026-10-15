# Phase 5: Compliance Mapper

## What this phase does

This module measures how semantically aligned a company's narrative
disclosure under each of the 9 BRSR principles is with that principle's
_official regulatory definition_ — using sentence-embedding cosine
similarity between the company's filed text and the exact wording of the
National Guidelines on Responsible Business Conduct (NGRBC), the
regulatory text SEBI's BRSR circular explicitly adopts as its 9-principle
framework.

Core files:

- `src/analysis/compliance_mapper.py` — contains the official 9-principle
  text and the alignment-scoring logic
- `scripts/05_compliance_mapper/inspect_compliance_mapper.py` and
  `validate_compliance_mapper_bulk.py` — verification scripts

## Why this approach (not alternatives)

**The regulatory text had to be sourced from public official documents,
not invented.** The project had access to SEBI's cover circular
(SEBI/HO/CFD/CMD-2/P/CIR/2021/562) confirming that BRSR is structured
around the 9 NGRBC principles, but the circular's own annexures
(containing the exact principle wording) were not directly available.
Rather than paraphrasing or approximating the principle definitions, the
exact official wording was located and cross-verified against multiple
independent public sources — the same wording appearing consistently
across 6+ unrelated websites was treated as strong evidence of genuine
quoted official text, not paraphrase, since independent sources
paraphrasing the same regulation would be expected to differ in wording.

**Why cosine similarity against the literal principle sentence, not a
larger reference corpus.** Each principle's official definition is a
single, dense sentence (e.g. "Businesses should respect and make efforts
to protect and restore the environment" for P6). Comparing a company's
narrative disclosure segment against this exact sentence — rather than
against a larger curated example set, as in Phase 4's vagueness detector
— was a deliberate simplification appropriate to this specific task: the
goal here is topical alignment with the principle's stated scope, not
distinguishing vague from specific language.

## Key decisions and trade-offs

**Trade-off accepted: this measures topical alignment, not legal
compliance.** A high similarity score means a company's disclosure under
a principle uses language and content thematically close to what that
principle is officially about (e.g. a P6 disclosure that discusses
emissions and resource restoration scores higher than generic corporate
boilerplate). It does not mean the company has met every mandatory
indicator under that principle — that is checked separately by the
Completeness, Specificity, and Truth Auditor components. This
distinction is stated explicitly in the module's own documentation
rather than left ambiguous.

**Decision: validate with a discrimination test, not just inspect raw
similarity scores.** Raw cosine similarity scores in this task are
naturally low in absolute terms (0.10-0.35 range) because the comparison
is between a long, specific disclosure paragraph and one short, abstract
principle sentence — low absolute magnitude does not by itself mean the
metric is broken. The real validity test built here checks something
different: does a company's P6-tagged text actually score _highest_
against P6's own definition, compared to the other 8 principles'
definitions? This is the metric that would reveal a broken or
non-discriminating system, independent of the raw score's magnitude.

## Real bugs found and fixed here

1. **Cross-principle boilerplate contaminated the discrimination test —
   the same underlying pattern found in Phase 2 and Phase 3, appearing
   here in a new context.** An initial single-sample discrimination test
   showed only 22.2% top-1 accuracy (barely above the 11.1% random-chance
   baseline for 9 classes), which was investigated rather than accepted
   as a genuine negative result. Every "worst-case" example text pulled
   for inspection turned out to be the identical boilerplate sentence
   (e.g. a Statutory Auditors disclosure) repeated across multiple
   principles — because Python's `set` iteration order is not guaranteed,
   an early version of the test script happened to repeatedly sample
   this non-discriminating boilerplate text via `list(texts)[0]`. Fixed
   the same way as Phase 2/3's related bug: deduplicating at the
   (company, concept, exact-text) level so text genuinely duplicated
   across principles for a company is excluded from the test entirely,
   and evaluating every available segment (not one arbitrary sample) for
   a statistically meaningful result.

2. **Bare URL/weblink text was included in the discrimination test,
   diluting the signal with semantically meaningless content.** A
   second-pass single-company test (Mastek Limited) still showed poor
   accuracy after the deduplication fix, and inspection showed the
   remaining "worst-case" text was mostly bare policy weblinks (e.g.
   `https://.../Code-of-Conduct.pdf`) — text with no narrative content
   for a sentence embedding to meaningfully compare against an abstract
   principle statement. Fixed by explicitly excluding text starting with
   `http://`/`https://` from the discrimination test, and by running the
   test across a bulk sample (100 companies, 393 total narrative
   segments after cleaning) rather than 1-3 individual companies, since
   small per-company sample sizes made the metric too noisy to draw any
   conclusion from on its own.

   **Result after both fixes: 44.3% top-1 accuracy vs. 11.1% random
   baseline (n=393)** — a real, 4x-above-chance signal, with sensible
   per-principle variation (Environment and Sustainable Products scored
   highest at 64-67%, reflecting their distinctive vocabulary;
   Stakeholder Engagement and Consumer Value scored lowest at 12-23%,
   reflecting their more generic corporate language).

## Your personal reflection (fill this in yourself)

_[This section is intentionally left for you to write in your own words.
Some starting questions to reflect on, based on the actual decisions
above:]_

- This is the second time in the project that the exact same underlying
  bug pattern (Python set iteration order exposing boilerplate text)
  caused a misleadingly bad initial result. Why do you think this
  pattern kept recurring across different modules, and what would you
  personally add to the project's testing process to catch it earlier
  next time?
- The 44.3%-vs-11.1% result is good relative to chance, but far from
  "accurate" in an absolute sense. How would you personally explain this
  number's value to a skeptical examiner who says "44% doesn't sound
  very good"?
- Sourcing the exact official NGRBC wording (rather than paraphrasing it
  yourself) mattered for this module's credibility. Why do you think
  using the company's actual regulatory language, instead of an
  approximate description, was worth the extra effort of verifying it
  across multiple sources?
