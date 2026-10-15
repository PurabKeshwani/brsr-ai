# Phase 6: Transparency Score (Composite Scoring + Peer Benchmarking)

## What this phase does

This phase combines outputs from every earlier phase into a single
composite "Transparency Score" (0-100) per company, following the
report's stated formula:
`TS = 0.40×Completeness + 0.30×Specificity + 0.20×Clarity + 0.10×SDG_Alignment`.
It also builds sector-level peer benchmarking (percentile ranking within
a company's own industry) and, separately, validates the composite score
against independent human judgment.

Core files:

- `src/analysis/completeness_score.py` — Completeness component
- `src/analysis/specificity_clarity_score.py` — Specificity and Clarity
  components (reused from Phase 4's vagueness/KPI detection)
- `src/analysis/sdg_alignment.py` — SDG Alignment component
- `src/analysis/transparency_score.py` — combines all four into the
  composite score
- `src/analysis/sector_classification.py` and `src/analysis/
peer_benchmarking.py` — NIC-code-based sector grouping and percentile
  ranking
- `scripts/06_transparency_score/bulk_transparency_scoring.py` — scores
  all 1,164 ingested companies
- `scripts/06_transparency_score/export_human_validation_sample.py` and
  `compute_pearson_correlation.py` — the human-validation study

## Why this approach (not alternatives)

**Each component's denominator had to be derived from the project's own
data, not assumed from an unavailable official source.** The original
report's formula referenced "SEBI's 140 mandatory BRSR questions" as
Completeness's denominator — a specific official count this project did
not have access to. Rather than guessing at that number, Completeness is
computed against a data-derived "concept universe": the union of every
distinct XBRL concept observed across all ingested filings, on the
reasoning that since every filer uses the same SEBI-mandated taxonomy,
this union approximates the full set of concepts a maximally complete
filing could report. This is disclosed explicitly as a methodological
substitution — data-derived rather than sourced from an official
question count — not presented as matching the report's exact original
formula.

**SDG Alignment measures disclosure _depth_, not just presence, after an
early design flaw made it a non-discriminating "dead" component (see Bug
Fixes Log).** The final design only counts a principle toward SDG
coverage if it has at least one KPI-backed (quantified) disclosure
segment, not merely "some text exists under this principle" — because
all 9 principles are SEBI-mandatory and every company files something
under all of them, a presence-only design produced an identical SDG
score for every company regardless of actual disclosure quality.

**Why human validation was run separately from the automated pipeline.**
The report's original methodology cites a Pearson correlation (r=0.84)
between AI-generated scores and independent human ESG analyst scores as
validation. This project could not replicate an independent-expert-panel
study at that scale, so a smaller, transparently-scoped version was run
instead: 20 companies, stratified across the full range of computed
Transparency Scores (not randomly sampled, to ensure the correlation
study covers both high- and low-scoring companies rather than clustering
near the average), each independently rated 0-100 by reading a summary
of the company's actual disclosure text. This is disclosed as
LLM-assisted scoring, not independent human-analyst scoring — an honest
methodological difference from the report's originally stated approach,
stated plainly rather than implied to be equivalent.

## Key decisions and trade-offs

**Trade-off accepted: Specificity uses a simpler KPI-presence rate, not
the report's exact "KPI density / 2.0" formula.** The report's original
Specificity formula scaled total KPI-entity counts by an empirically-
chosen "2.0 KPIs per segment" denominator this project had no basis to
replicate. Instead, Specificity is computed as the fraction of narrative
segments containing at least one KPI/numeric entity — a simpler, more
directly interpretable rate, disclosed as a deliberate simplification.

**Decision: 1,164 companies scored, giving a real score distribution to
validate against**, rather than computing scores for only a handful of
example companies. This let genuine distributional properties be
checked directly — e.g. whether large, established companies (Tata
Steel, Tata Chemicals) score higher than smaller/newer ones (Aditya
Vision Limited), which matched intuitive expectations and served as an
informal sanity check before the formal human-validation study.

## Real bugs found and fixed here

1. **Completeness incorrectly penalized valid short/structured
   answers.** A word-count threshold (from the report's stated "fewer
   than 10 words counts as trivial" rule) was applied too broadly,
   marking a company's full, valid address as "trivial" simply because
   it had fewer than 10 whitespace-separated tokens despite being a
   complete, specific answer. A second issue: "0" was blanket-treated as
   a non-answer, which incorrectly discarded genuine numeric disclosures
   of zero (e.g. a company correctly reporting zero differently-abled
   employees). Both were confirmed by directly inspecting a specific
   company's (Aditya Vision Limited) raw facts and checking which ones
   were being classified as trivial. Fixed by scoping the word-count
   check to only narrative/text-block concepts (where it was actually
   designed to apply) and by only treating "0" as trivial for narrative
   concepts, not structured numeric fields.

2. **SDG Alignment was a non-discriminating "dead" component — every
   company received an identical score.** The original design counted a
   principle as "covered" if any non-trivial text existed under it.
   Since all 9 principles are SEBI-mandatory and every ingested company
   files something under each one, every company scored an identical
   82.35% on this component regardless of actual disclosure quality —
   confirmed by directly testing three companies of very different sizes
   (NIIT, Mastek, Aditya Vision) and finding all three returned exactly
   the same value. Fixed by requiring a principle's disclosure to
   contain at least one KPI-backed segment (reusing Phase 4's
   `has_kpi` check) to count toward SDG coverage, which produced
   genuinely differentiated scores afterward (11.76% to 64.71% across
   the same three test companies).

3. **The human-validation correlation was initially weak and not
   statistically significant (r=0.30, p=0.19) — investigated as a
   likely sampling artifact rather than accepted as a genuine negative
   finding about the score's validity.** Comparing per-company
   differences between AI and human scores showed the largest
   disagreements clustered on companies with very large total filings
   (DLF: 69 segments, Zensar: 56, Eureka Forbes: 51). Root cause:
   `export_human_validation_sample.py` took the first N segments in
   database query-order, which for large filings happened to be
   dominated by bare policy weblinks — giving the human rater an
   unrepresentative, weblink-heavy view of what those companies actually
   disclosed, and producing artificially low human scores for otherwise
   well-documented companies. Confirmed directly by querying the actual
   total segment count for the worst-mismatched companies. Fixed by (1)
   excluding bare-URL segments explicitly and (2) sampling randomly
   rather than taking the first N in query order. **Result after the
   fix: r=0.6314, p=0.0028 — statistically significant**, with the
   Spearman rank correlation (rho=0.6285, p=0.003) independently
   confirming the relationship wasn't a linear-outlier artifact.

## Your personal reflection (fill this in yourself)

_[This section is intentionally left for you to write in your own words.
Some starting questions to reflect on, based on the actual decisions
above:]_

- The SDG Alignment bug produced a score that looked completely
  plausible (82.35%, a reasonable-seeming number) while being
  completely useless (identical for every company). What does this
  teach you about the danger of only checking whether a number "looks
  reasonable" versus checking whether it actually varies meaningfully
  across different inputs?
- The human-validation correlation went from not-significant (r=0.30) to
  significant (r=0.63) purely by fixing a sampling bug — the underlying
  Transparency Score itself never changed. If you had to explain this to
  someone who only saw the final r=0.63 result, how would you honestly
  frame the fact that an earlier version of the same experiment gave a
  much weaker number?
- Several of this project's formula components deliberately simplify the
  report's original mathematical definitions (Completeness's denominator,
  Specificity's KPI-density calculation). Do you think disclosing these
  as "deliberate simplifications" is the right way to handle it, versus
  either forcing an exact match to the original formula or hiding the
  difference? What would you say if a mentor pushed back on this in the
  viva?
