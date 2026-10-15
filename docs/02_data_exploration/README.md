# Phase 2: Data Exploration & Weak-Supervision Verification

## What this phase does

Before building any BERT classifier, this phase answers a foundational
question: **can the ingested XBRL data provide training labels without
manual annotation?** SEBI's XBRL taxonomy tags every narrative text block
with a `PrincipleAxis` dimension (one of the 9 BRSR principles), and this
phase verifies whether that tagging is consistent and reliable enough to
use as a free label source — instead of the traditional approach of
paying human annotators to read and label thousands of text segments.

Core files:

- `scripts/02_data_exploration/inspect_principle_labels.py` — checks
  whether `PrincipleAxis`-labeled text exists consistently across every
  ingested company, and whether the resulting class distribution is
  balanced
- `scripts/02_data_exploration/inspect_duplicate_concepts.py` — a
  follow-up diagnostic that investigates a suspicious duplication pattern
  found later during dataset construction (see Bug Fixes Log)

## Why this approach (not alternatives)

**The alternative was manual annotation** — the approach most comparable
academic work uses: recruit domain experts, have them independently
label thousands of text segments against the 9 BRSR principles, measure
inter-annotator agreement (Cohen's Kappa), and use the resulting labeled
set to train a classifier. This is the gold-standard approach, but it
requires significant time and multiple trained annotators working in
parallel — a scale of effort not realistic within this project's
timeline with a 4-person team.

**The insight: SEBI's own taxonomy already provides this label, for
free, at the source.** Because BRSR's XBRL format requires every
narrative disclosure to be tagged with which of the 9 principles it
addresses (this is mandatory under the reporting format, not optional
metadata), every company's filing already contains its own
principle-labeled text — assuming the tagging is applied consistently.

This phase exists specifically to test that assumption _before_ trusting
it, rather than assuming it and finding out later that it was unreliable.
The verification checked: (1) does every company have at least some
`PrincipleAxis`-labeled text, and (2) is the resulting 9-class
distribution roughly balanced, or does it skew heavily toward a few
principles (which would make classifier training much harder).

**Result, on the initial 74-company sample:** 0 companies had zero
labeled text, and the distribution across the 9 principles was tight —
ranging from 284 to 303 samples per class, out of 2,626 total
labeled facts (out of 6,704 total narrative text facts — meaning roughly
39% of all narrative text carried a usable principle label). This
confirmed the weak-supervision approach was viable, and the project
proceeded to build the full training dataset on this basis
(`scripts/03_bert_training/build_training_dataset.py`), described in the
paper as "weak supervision from regulatory taxonomy structure" — a
distinct, disclosed methodology, not a claim of manual annotation.

## Key decisions and trade-offs

**Decision: verify before building, not build then discover problems.**
This phase's entire purpose is a sanity-check gate — running a small,
fast diagnostic script (`inspect_principle_labels.py`) before committing
to writing the full training pipeline, so that if the weak-supervision
assumption had failed (e.g. if most companies had zero labeled text, or
one principle dominated 90% of samples), the project could pivot before
investing further time.

**Trade-off accepted: this labeling approach is coarser than manual
annotation.** Weak supervision from a regulatory taxonomy tag is not the
same guarantee as an expert reading a sentence and deciding which
principle it addresses — a filer's own `PrincipleAxis` tagging could,
in principle, be wrong or inconsistent for a specific segment. This is
disclosed explicitly rather than presented as equivalent to
expert-annotated ground truth.

## Real bugs found and fixed here

1. **Cross-principle boilerplate duplication (discovered via
   `inspect_duplicate_concepts.py`, after an earlier symptom appeared
   during dataset construction).** When the full training dataset was
   first built, 1,212 of 1,648 training rows (73%) turned out to be
   exact-duplicate text assigned _conflicting_ principle labels — the
   same sentence tagged as both `Principle1` and `Principle7`, for
   example. This diagnostic script was written specifically to find the
   root cause: which XBRL concepts were responsible. It found that 5
   specific concepts (weblink-to-policies, specific
   commitments/goals/targets, performance-against-commitments, national/
   international certifications, and independent-assessment-agency
   fields) accounted for ~2,060 of the ~2,360 total duplicate-label
   instances in the dataset. These are Section B "administrative
   metadata" fields — a company files one blanket policy weblink or
   commitment statement, and SEBI's form structure replicates it
   identically across all 9 principles.

   **This directly informed a downstream fix** in
   `03_bert_training/build_training_dataset.py`: rather than blanket-
   excluding these 5 concepts (an initial over-aggressive attempt that
   discarded 98.8% of the dataset, since the same concepts also held some
   genuinely unique content), the fix deduplicates at the
   (company, concept, exact text) level — discarding only text that was
   _actually_ found tagged under more than one principle for that
   specific company, while keeping text that happened to come from the
   same concept type but was genuinely unique per company.

## Your personal reflection (fill this in yourself)

_[This section is intentionally left for you to write in your own words.
Some starting questions to reflect on, based on the actual decisions
above:]_

- The weak-supervision idea (using XBRL's own tags instead of manual
  labeling) was a significant methodological choice for the whole
  project. Looking back, what convinced you this was a valid substitute
  for manual annotation, and what would you tell someone who challenged
  it as "not real ground truth"?
- The duplicate-boilerplate bug wasn't caught in this exploration phase
  — it only surfaced later, when the training loss looked wrong. Should
  a check for exact-duplicate text have been part of this initial
  verification step? What would you add to this phase if you did it
  again?
- 39% of narrative text ended up being usable (having a PrincipleAxis
  tag). Does that number surprise you? What do you think the remaining
  61% of narrative text actually contains?
