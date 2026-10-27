# Journal manuscript revision

Prepared: 2026-10-21.

## Scope completed

- Converted `paper/main.tex` from IEEE conference layout to a generic A4, 11 pt, single-column journal manuscript with 23 mm margins, numbered sections, readable captions, and multipage tables.
- Preserved the original source in `main_before_journal.tex.txt`.
- Rewrote the complete narrative using plain professional English and explicit subjects. Personal pronouns and the prohibited word were removed from included manuscript sources.
- Expanded BRSR on first appearance in the abstract, described existing method mechanisms and limitations, and specified the seven-module pipeline.
- Rebuilt the introduction around the analyst's manual workflow, three clearly explained questions, qualified novelty, and a separate section-outline paragraph.
- Expanded the literature comparison to 16 studies with the requested columns: Year, Objective, Methodology, Main Findings, Scope/Limitation, Inference Drawn. The multipage table follows the review text without floating into another section.
- Verified bibliography metadata against primary sources. Corrected the Shankar/Xu citation to an SSRN working paper, the Garg citation to an IIMA institutional report, and the Vinella citation to the actual language-model paper. Removed unsupported reference identities from the earlier manuscript.
- Removed stage numerals from methodology subsection headings. The overview diagram retains module numbers for navigation.
- Explained each module's inputs, internal decisions, outputs, and evidence limits.
- Replaced the architecture artwork with an editable three-column input/process/output diagram with fourteen straight, non-crossing arrows. A detailed optional raster-generation prompt is in `paper/diagram_generation_prompt.md`.
- Replaced stale classifier, detector, and alignment results with the consolidated final audit values and available confidence intervals. No result from `results/improve/` enters the manuscript.
- Added simple English explanations of precision, recall, F1, Top-1, Top-2, support, and cluster confidence intervals without binary error-category jargon.
- Replaced old pilot learning curves with source-specific results, the actual five-epoch seed-99 validation history, per-principle F1, concept holdouts, and separately labelled detector cohorts.
- Replaced the unsupported feature-importance presentation with an interpretable weighted-component figure. The new Figure 7 explains exactly how the four bars sum to the worked Transparency Score.
- Corrected Completeness to all observed concept types rather than numerical items only. Added its exact denominator, response rules, treatment of zero, and applicability limitation.
- Explained Specificity as evidence-pattern presence, Clarity as absence of a detector flag, and SDG breadth as a fixed correspondence. Documented the 14-of-17 goal ceiling and the principle-retention limitation in current deduplication.
- Described the 40/30/20/10 coefficients as fixed implementation heuristics because a SEBI prescription was not verified.
- Reorganised application results into four levels: one company; selected financial companies and available years; the complete 94-company financial group; and all 72 recorded sector groups.
- Added all 94 financial company rows, every component, reconstructed year labels, and percentiles. Added all 72 sector groups, population sizes, score distributions, and the five-company comparison threshold.
- Preserved uncertainty about original rating blinding, test reuse, weak labels, legacy pretraining exposure, numerical verification, and API evaluation scope.
- Added a source-hash and descriptive-data manifest. No training, model inference, or terminal command was executed during the revision.

## Requested epoch extension: evidence unavailable

The old Figure 3 showed a four-epoch pilot. The selected final model has five recorded fine-tuning epochs, with epoch 4 selected on validation macro-F1. Two additional epochs beyond the pilot would require a six-epoch experiment; no completed six-epoch result is available in the audited final artifacts. The revised figure therefore plots the five actual recorded epochs and does not extend the curve with invented values. The comment requesting two additional experimental epochs remains pending as an experimental request, not a formatting task. No new experiment was started.

## Evidence resolution

The supplied pasted assessment contains historical recommendations for 93.83% classifier accuracy, F1 0.923, the 393-segment alignment result, and synthetic weight findings. Later audit artifacts supersede those recommendations. The manuscript uses the final recovered 93.00% classifier result, development detector F1 0.7436, same-row supervised/zero-shot mapping comparison, and the 20-company human-rating association. The exploratory multi-label diagnostic retains its changed target definition.

## Descriptive snapshot verification

Saved score rows: 1,164 unique CINs. Recorded sector groups: 72. Groups with at least five companies: 47, containing 1,109 companies. Other groups: 25, containing 55 companies. Financial-services group: 94 companies, with reconstructed latest-filing end years 2026 for 77 and 2025 for 17. The original score CSV omitted filing IDs, so reconstructed year linkage is explicitly qualified.

The worked Triveni example reconciles to filing 197: 1,862 raw facts, 613 accepted concepts out of 1,057, and 52 narrative concept/text pairs. Saved component arithmetic rounds to 68.91. The three numerical fact pairs reproduce database values without changing values or running verification models.

Current database record counts are described as snapshot metadata. The historical 1,164/1,276 coverage claim remains qualified and is not converted into audited ingestion accuracy.

## Interpretation corrections

- Numerical matching and assurance checks have no complete validation metric. Current code has context and zero-handling limitations, which are disclosed rather than silently repaired in a paper-only revision.
- Source differences support caution about generalisation but do not prove a unique causal explanation for the complete accuracy gap.
- Sector standard deviations are descriptive spread, not confidence intervals. A low sector score is not a finding of greenwashing.
- The saved seed-99 Trainer history records epoch-4 validation macro-F1 as 0.919368, while the historical trial summary rounds a later validation result to approximately 0.9195. The training plot uses the exact saved epoch history and the headline uses recovered test results, avoiding an unsupported merger of the two records.
- A verified API request establishes one runtime integration case and supplies no cohort-level accuracy estimate.

## Verification status

Source-language, citation-key, numeric-source, table-count, and LaTeX layout checks are recorded in `verification.json` when complete. Built-in LaTeX compilation is used where available. The user's terminal-only execution constraint remains in effect for shell commands and model runs.

## Model history and comparative-evaluation addition

- Clarified the base-BERT, BRSR adaptation, supervised fine-tuning, and recovered-checkpoint sequence, with separate MPNet and historical ClimateBERT/ensemble roles.
- Described the mapping service as softmax probability reuse from the existing nine-output classifier.
- Added a compact comparison table with source-specific, excluded-concept, and zero-shot versus supervised results, sample counts, and interpretation limits.
- Made the seed-99 versus seed-42 difference explicit in the concept diagnostic and stated that no matched plain-BERT versus adapted-BERT ablation is available on the final partition.
- Retained the approved audit values and excluded causal claims for cleaning or adaptation from unmatched historical experiments. No training, inference, or terminal command was run.

## 2026-10-22: compact tables and old-paper reconciliation

- Integrated the supplied grasp_pipeline.png, verified all seven titles, and updated the workflow caption to explain the main routes and secondary dependencies.
- Compacted main-text Tables 12 and 13; exact caption+table bounds passed the LaTeX one-page check. Complete financial and sector records remain in S1 and S2.
- Restored the complete eight-company paired-year comparison in Table 11 and preserved all 16 component rows in S3. Added the Pharmaceuticals contrast to the narrative and seven detailed examples to S4.
- Removed former Section 6.5 and the artifact-location table from the manuscript.
- Rewrote the conclusion with audited metrics, descriptive company/sector/year findings, and a final future-work paragraph.
- Compared all nine pages of the supplied old PDF; rendered pages 7–8 for the historical application-result layouts. The revised full PDF could not be exported for a page-by-page visual pass.
- Produced request_audit_and_old_paper_comparison.md: 22 populated writing requests implemented; the requested six-epoch result remains unavailable. The historical 84-check arithmetic claim has no located supporting audit artifact and was not restored.
- No terminal command, training, model inference, or new predictive metric was run.

## Methodology opening pagination fix

Removed the separate-page figure float and the following float barrier that left the opening paragraph alone. The methodology heading, introduction, nonfloating diagram, and shorter caption now form one unbreakable minipage. The image height is capped at 62% of the text height. An exact box-dimension check and the main manuscript compilation both passed. No image content, audit number, training, inference, or terminal command changed.

## Larger diagram on a dedicated methodology overview page

Kept the methodology heading, introductory paragraph, Figure 1, and caption together on a dedicated page. Increased the image height cap from 62% to 72% of the text height, shortened the caption to 25 words, and forced the first methodology subsection to the following page. The main manuscript includes an exact opening-box height guard and compiled successfully. The current editor remained open; no separate document was compiled for this change.

## Literature-table overflow removed

Removed the Snorkel and general leakage-review rows from the comparison table, leaving 14 selected studies. Both citations and their discussion remain in the prose. Compilation with a temporary page-counter assertion verified the methodology overview starts on page 6; the assertion was removed and the final main manuscript compiled successfully.

## Full-paper plain-language pass

Reduced the abstract to 204 words, kept the full seven-part pipeline, and retained only the main classifier and score-validation findings in the abstract. Rewrote all narrative sections and simplified literature cells, captions, metric explanations, and score descriptions. Added short definitions for required technical terms. Numeric table entries and equation blocks are unchanged. In-place checks confirmed the methodology remains on page 6 and compact Tables 12 and 13 fit one page. Only the existing main document was compiled; no replacement PDF or new tab was created.

## Positive presentation and eight-request audit

The current abstract contains 176 words and highlights all seven pipeline parts with two main results. Removed the abstract blinding sentence and the remain-necessary ending, replaced the Limitations headings with practical-use discussion, and consolidated repeated commentary across the paper. Material label, sample, annotation, and evaluation facts remain in the methods/evaluation sections. Future work starts with the requested multiple-levels sentence. eight_requested_changes_audit.md records completed requests and qualified reframing for requests 1, 5, and 6. Numeric tables and equations are unchanged. In-place layout checks passed for Methodology on page 6 and single-page Tables 12 and 13.

## Proposed Solution restored before Methodology

Read the historical reference PDF, page 2, and added sections/02a_proposed_solution.tex between the literature review and methodology. The new overview explains the shared filing record, the three design requirements, seven modules, and four reporting levels using the current implementation. Numerical review records remain separate from language flags; principle mapping uses classifier probabilities. Updated the introduction roadmap. The existing architecture figure and all result tables remain in place. The main document compiled successfully, with zero prohibited-word matches or unresolved source references. Earlier page-6 assertions describe the previous layout; absolute pagination was not rechecked after this section insertion. No terminal command, training, or model inference was run.

## Beginner-friendly abstract and terminology

Rewrote the abstract in simple professional English, removed XBRL, and retained the full pipeline and two main results. Report means the complete company BRSR document; text segment means a selected portion of report text used for analysis. Passage and sample are not used as synonyms in the revised abstract. The 6,201 test count explicitly refers to text segments, not reports or companies. Apply these definitions during later section-by-section edits; the rest of the manuscript has not yet received this terminology pass. The existing main document compiled successfully. No terminal command, training, or model inference was run.

## Beginner-friendly introduction

Rewrote the requested introduction paragraphs as three clearly separated design questions, each followed by the relevant GRASP approach. Explained labels, weak labels, reporting concepts, four score components, and the roles of training, validation, and test groups. Simplified the evaluation overview and section roadmap. Kept the opening reporting background and aligned terminology in the analyst-workflow and related-method paragraphs: report means the complete document; text segment means a selected text portion. No passage/sample synonyms remain in the introduction. All cited sources and the 42,409 count were retained. The open introduction file compiled successfully through the existing main document. No terminal command, training, or inference was run.

## Beginner-friendly Proposed Solution

Expanded the Proposed Solution into a clear overview of seven modules. Explained weak labels, BERT domain adaptation and masked language modelling, hedging lexicon, semantic similarity, classifier probabilities, zero-shot comparison, Transparency Score components, and the service/API role. Report denotes the complete company document; text segment denotes the selected analysis unit. Passage and sample are absent from the revised section. Retained AI-assisted mapping provenance, classifier reuse, separate language/numerical review outputs, and the four application reporting levels. Methodology headings, the supplied diagram, and result values are unchanged. The existing main document compiled successfully from the edited section path; the current editor was retained. No terminal command, training, or model inference was run.

## Proposed Solution restructured around the intervention

Replaced the earlier module-by-module explanation following user clarification. The current section presents the overall solution, connects three design choices to the introduction problems, explains architecture choices and required resources, distinguishes supervised BERT training from zero-shot MPNet, and states intended analyst benefits. The 1,164-company application coverage supports implementation feasibility; no cost, timing, superiority, or new performance result was invented. Detailed algorithms and training steps are referred to Methodology. Text segment remains the analysis unit. The existing document compiled successfully, and no replacement document or tab was opened.

## Methodology opening and Figure 1 caption

Replaced the opening explanation with a connected flow from BRSR report data to classifier training, review checks, score calculation, and API outputs. Removed the sentence about identical figure/subsection titles and the duplicate title-correspondence statement in the caption. The shorter caption names the inputs, outputs, and main connections. Kept the supplied image, dimensions, dedicated overview page, and later methodology subsections unchanged. The existing main document compiled successfully, including the overview-box height guard.

## Generated diagram with detector reuse

Used the existing grasp_pipeline.png as the input to the built-in image generation tool. Preserved the seven numbered module titles and icon/palette style, and rearranged the review/scoring branch to show a direct dashed 4-to-6 dependency labelled Detector reuse for Clarity (20%). Solid data/model/result routes converge at the service layer; the generated image was visually checked for correct labels and non-crossing routes. Installed the selected image at the existing paper asset path, preserving the original image and original prompt in 2026-10-26_before_detector_reuse. Updated the Figure 1 caption and the Clarity paragraph to explain detector reuse. The exact generation prompt is in paper/diagram_generation_prompt.md. The current main document compiled successfully, including the overview height guard. No model-training, predictive inference, scoring-code change, or terminal command was performed.

## Discussion and Practical Use removed

Removed the complete Discussion and Practical Use section, its main-document input, and the corresponding introduction-roadmap sentence. The original section and affected source versions are preserved in 2026-10-26_before_discussion_removal. Results now leads directly to Conclusion, with the existing Results float barrier retained. No active manuscript reference to the removed section remains. The current main document compiled successfully; all active cross-references resolve.
