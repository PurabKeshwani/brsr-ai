# Eight-request manuscript audit

Prepared: 2026-10-22.

## Revision approach

The paper now uses direct, positive wording and focuses on the pipeline, findings, calculations, and practical use. Repeated warnings and the dedicated Limitations headings were removed.

Requests 1, 5, and 6 were applied as reframing and consolidation, not blanket deletion of material study conditions. Label sources, test populations, annotation procedures, and the component measured by a result remain documented. The revision does not describe undocumented human ratings as blind or independently validated.

## Request-by-request status

| No. | Requested change | Status | Actual change |
|---:|---|---|---|
| 1 | Remove discussion of the paper's limitations | Reframed; essential facts retained | Removed the dedicated Limitations section title and negative subsection titles. Reduced repeated self-critical commentary across the introduction, methods, results, discussion, captions, and conclusion. Necessary data and method conditions remain in the relevant sections. |
| 2 | Remove the automated-score-unconfirmed line from the abstract | Completed | Removed that line. The rating procedure is recorded once in the evaluation section. |
| 3 | Remove the abstract's “remain necessary” ending | Completed | Replaced the ending with the practical use of linked passages, score breakdowns, and peer comparisons. |
| 4 | Highlight the full pipeline in the abstract | Completed | The 176-word abstract covers structured filing collection, label construction, BERT adaptation/classification, language and numerical review, principle mapping, Transparency Score/sector comparison, and the API. |
| 5 | Remove human-rating limitations | Consolidated; essential facts retained | Removed repeated rating caveats from the abstract, discussion, and conclusion. One factual evaluation paragraph retains the 20-company sample, one documented rating source, undocumented blinding, and the original case conditions. |
| 6 | Avoid self-critical wording throughout | Reframed; essential facts retained | Replaced repeated negative commentary with method definitions, recorded evaluation conditions, descriptive results, and practical-use explanations. Material facts were not erased or replaced with stronger validation claims. |
| 7 | Begin future work with the requested sentence | Completed | The final conclusion paragraph begins exactly: “This work can be extended using multiple levels.” Data, modelling, numerical review, annual reporting, and framework extensions follow. |
| 8 | Remove They, Them, Their, We, Project, and similar words | Completed | Case-insensitive whole-word scan of all 16 included TeX files found zero prohibited personal-pronoun or whole-word matches. |

## Current paper structure

- Abstract: full seven-part pipeline, two main findings, and practical use.
- Introduction: review task, workflow requirements, and contribution.
- Methods: actual inputs, labels, model training, decision rules, score calculations, and service outputs.
- Evaluation: measured results and the recorded conditions needed to interpret each result.
- Application results: company, financial-sector, all-sector, and paired-year outputs.
- Discussion and Practical Use: how outputs connect and how an analyst uses the results.
- Conclusion: supported findings, company/sector/year summaries, and level-wise future work.

The literature table retains the Scope / limitation column for the cited external studies, as requested in the earlier table specification.

## Evidence preserved

- Taxonomy-derived weak labels and the 29 AI-assisted mappings.
- Company-separated supervised training, with checkpoint-specific adaptation membership not verified.
- Reuse of the same classifier test result in principle mapping.
- Different seeds and training examples in the excluded-concept comparison.
- Development status of the 80-example detector group and AI provenance of the 70-example comparison.
- The 20-company historical rating group, documented source count, and unrecorded blinding.
- The numerical branches' evaluation scope and the recorded fact-selection/zero-handling rules.
- Current metric tables, confidence intervals, and equations.

## Checks

- Numeric table entries: unchanged.
- Equation blocks: unchanged.
- Prohibited-word scan: zero matches.
- Undefined references/citations and duplicate labels: zero.
- Methodology start: page 6, checked during compilation of the existing main document.
- Tables 12 and 13: current caption-and-table boxes fit one page.
- Main-document compilation: final status recorded in verification.json.
- Terminal commands, training, model inference, and new predictive evaluation: not run.
- Revised full-PDF visual review: not performed; the built-in compiler supplies diagnostics without an accessible PDF export.

Sources were edited in place. The open main document was retained, and no replacement document or separate PDF was created.
