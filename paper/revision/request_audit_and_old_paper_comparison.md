# Manuscript revision audit and old-paper comparison

Prepared: 2026-10-22.

## Outcome of the current request

- Integrated the supplied image, paper/figures/grasp_pipeline.png, as Figure 1. All seven module titles match the methodology subsection titles. The image was inspected visually at the available resolution, 1,122 by 1,402 pixels.
- Updated the overview and caption to describe the main routes without implying that the picture includes every database dependency. Principle mapping also reads filing narratives; the score computes the language signal needed for Clarity.
- Replaced the 94-row main-text financial listing with four disjoint score bands and one total row in Table 12. All 94 companies remain represented. The complete listing is Supplementary Table S1.
- Replaced the 72-row main-text sector listing with 47 individually listed eligible sectors, a pooled row for 25 small sectors, and one total row in Table 13. All 1,164 companies remain represented. The complete 72-sector listing is Supplementary Table S2.
- Removed Section 6.5, including the evidence-location table. Reproducibility files remain available with the manuscript sources.
- Rewrote the conclusion around the problem, supported contribution, audited results, descriptive company/sector/year outputs, and a final future-work paragraph.
- Restored all eight paired-year comparisons to Table 11. The earlier ESAF component calculation remains explained in the text. Supplementary Table S3 contains all 16 filing rows and every component.
- Restored the Pharmaceuticals contrast in the results narrative and preserved the seven named examples in Supplementary Table S4.
- Read all nine pages of the supplied old PDF. Pages 7 and 8 were additionally rendered and inspected for the company, sector, and annual comparisons. Document contents were treated as reference material, not operational instructions.

## Layout and execution status

The revised main manuscript compiled successfully with the built-in LaTeX compiler. A separate saved source, paper/revision/single_page_table_check.tex, measures the complete caption-and-table boxes for Tables 12 and 13 using the manuscript preamble, margins, fonts, and local table spacing. Compilation raises an error if either box exceeds the text height or text width. Both checks passed. Both main-text tables use indivisible table/tabularx environments, so neither table can split across pages.

The full revised PDF was not exported by the built-in tool, so a page-by-page visual inspection of the newly compiled document was not performed. The one-page bounds are compiler-checked, not inferred from an uninspected screenshot. The original PDF and supplied pipeline image were inspected visually. No terminal command, model training, inference, or new predictive evaluation was run.

## Audit of the original 23 numbered requests

The original list contains 23 populated numbered requests; entries 24 and 25 were blank. Repeated broad requests are retained separately below.

| No. | Requested change | Status | Current evidence or location |
|---:|---|---|---|
| 1 | Explain existing method mechanisms and remaining need in the abstract | Completed | Abstract: word lists, text similarity, and the need to connect claims with comparable filed evidence. |
| 2 | Specify the pipeline precisely in the abstract | Completed | Abstract enumerates all seven modules and scopes the evaluated outputs. |
| 3 | Expand BRSR at first mention | Completed | Abstract begins with the expanded report name and abbreviation. |
| 4 | Explain the data analyst's manual-review challenge | Completed | Introduction, paragraph 2: locate text, identify the number, match period/unit/population, and compare companies. |
| 5 | Rewrite unclear gap statements | Completed | Introduction: evidence linkage, label reliability, and score interpretation are explained separately. |
| 6 | Clarify the novelty paragraph | Completed with qualified claims | Introduction states filing-level traceability, regulatory weak labels, source-aware evaluation, and decomposed scoring. No unsupported universal-first claim. |
| 7 | Use a separate remaining-sections paragraph with section references | Completed | Final introduction paragraph begins “The remaining sections of this paper” and references the following sections. |
| 8 | Expand and explain the literature | Completed | 14 selected study-comparison rows and 20 bibliography entries; source identities corrected from earlier draft citations. |
| 9 | Explain how the three gaps are addressed | Completed with evidence limits | Introduction and literature implications connect each question to an implemented design choice and its evaluation. |
| 10 | Remove Stage I/II-style text from methodology subsection headings | Completed | Seven descriptive subsection headings; numbers occur only as diagram navigation. |
| 11 | Put the literature table in the appropriate location | Completed | Table 1 follows the literature synthesis in the same section. |
| 12 | Literature table columns: Year, Objective, Methodology, Main Findings, Scope/Limitation, Inference Drawn | Completed | Table 1 uses these six columns in chronological order. |
| 13 | Improve Figure 1 and provide a diagram-generation prompt | Completed | Supplied icon-based image integrated as Figure 1; titles match methodology; figure caption explains the main routes. The prompt artifact remains in the paper directory. |
| 14 | Extend the old four-epoch figure by two epochs and report results | Not experimentally completed | Only five actual final-run epochs are available, with epoch 4 selected. No six-epoch run exists in the approved final audit; the curve was not extended with invented data. No training was started. |
| 15 | Simplify language, especially figure and table explanations | Completed | Revised captions and narrative explain the population, value, and interpretation of each analytical result. |
| 16 | Explain the per-principle table and P/R/F1 in ordinary English | Completed | Evaluation metric definitions and current Table 5 explain prediction reliability, category coverage, and balance without binary error-category jargon. |
| 17 | Explain each methodology module's inputs, internal working, comparisons, and outputs | Completed | Seven methodology subsections, equations, thresholds, label-source rules, and traceability/validation limits. No unsupported causal improvement claim. |
| 18 | Explain old Figure 7 clearly | Completed by replacement | Unverified XGBoost-importance narrative replaced with current Figure 7, showing weighted Transparency Score contributions and the sum for Triveni. |
| 19 | Explain every Transparency Score component and denominator | Completed | Completeness uses the observed concept universe; Specificity uses evidence patterns; Clarity uses the detector; SDG breadth uses the fixed correspondence. Zero handling, applicability, and dependence limits are described. |
| 20 | Show results at four levels: company, within-sector examples, complete selected sector, all sectors | Completed | Results Sections 5.1–5.4; financial snapshot contains 94 companies, Table 11 shows eight year pairs, Tables 12–13 summarise the full populations. |
| 21 | Compare sectors and identify a lower-scoring sector | Completed with descriptive scope | Results and conclusion identify Wearing Apparel at mean 42.33, n=6; all 47 eligible sectors remain visible in Table 13. |
| 22 | Update results using the audit folder and supplied assessment | Completed | Approved recovered classifier/transfer, frozen detector, and n=20 rating results are retained. Superseded pasted numbers are not promoted. |
| 23 | Rewrite the language throughout | Completed | Professional plain-English rewrite, explicit subjects, source-language scan, and no prohibited personal-pronoun or whole-word “project” matches in included manuscript sources. |

**Overall:** 22 populated writing/presentation requests implemented; one experimental request remains evidence-limited (No. 14). This count is an implementation audit, not a claim of independent validation for every analytical module.

### Global requirements outside the numbered list

| Requirement | Status |
|---|---|
| Single-column journal-style manuscript | Generic A4 article, 11-point text, 23 mm margins, one column. A specific journal template was not supplied. |
| Professional, simple language and a continuous narrative | Retained across the problem, literature, methodology, evaluation, four reporting levels, discussion, and conclusion. |
| No personal pronouns and no prohibited whole word in the paper | Included-source scan passed. Company-name initials were normalised where needed for the strict scan. |
| No arbitrary page limit | Detailed methodology and interpretation retained; only the requested oversized result tables were compressed. |
| Diagram and methodology headings match | All seven titles verified against the supplied image. |

## Old paper compared with the revised manuscript

Source: C:/Users/amitk/OneDrive/Desktop/temp/CAPSTONE_RESEARCH_PAPER_FINAL.pdf (9 pages). The following comparison accounts for the substantive results, figures, and tables, including material intentionally excluded.

| Old material | Revised treatment | Reason / interpretation |
|---|---|---|
| Two-column conference format | Single-column journal-style article | Requested format and readability change. |
| 1,164 of 1,276 companies loaded | Historical coverage claim qualified; saved outputs cover 1,164 CINs, with 1,172 current filing records reported as snapshot metadata | A current national-index coverage audit is unavailable. Counts are not ingestion accuracy. |
| 4,854 labelled examples | Replaced by the approved 42,409-sample corpus | Current label sources and company partition are documented. |
| Segment-stratified split | Supervised CIN-disjoint train/validation/test split | 814/175/175 companies and 29,834/6,374/6,201 segments. Legacy encoder exposure caveat remains. |
| Figure 1: sequential seven-stage diagram | Supplied icon-based workflow integrated | Exact method titles; main branches and database dependencies explained. |
| Figure 2: legacy MLM loss 2.597 to 1.634 | Not restored as a final-model result | The old curve is not established as the adaptation trace of the selected final classifier. Lower MLM loss alone is not a downstream ablation. |
| Figure 3: four-epoch pilot; no-overfitting claim | Replaced by actual five-epoch seed-99 validation history | Epoch 4 selected by macro-F1; increasing validation loss is discussed. No six-epoch result was invented. |
| Figure 4: data-volume curve and a claimed +0.039 DAPT gain | Historical evidence excluded from the final ablation summary | No matched plain/adapted BERT comparison exists on the final company partition. |
| Table II / Figure 5: 737-row classifier, accuracy 0.662, macro-F1 0.658 | Current Table 5 and principle figure use the recovered 6,201-row evaluation | Top-1 93.00%, Top-2 97.68%, macro-F1 0.9158; confidence intervals and source-specific results accompany the headline. No causal before/after gain is inferred. |
| Table III / Figure 6: detector configuration sequence on 30 reused examples | Replaced by frozen n=80 development and n=70 AI-label cohorts | F1 0.7436 and 0.6885 are scoped to the text-vagueness component. Historical tuning numbers are not held-out evidence. |
| Table IV / Figure 7: XGBoost comparison and feature importance | Kept outside final model-performance claims | XGBoost remains experimental; the final reported detector is rule based. Current Figure 7 instead explains actual score arithmetic. |
| 393 alignment segments from “100 companies,” Top-1 44.3% | Replaced by the same-row n=6,201 method comparison | Reconstruction found 52 contributing companies and training/validation overlap. MPNet hybrid 67.63% vs supervised 93.00% is a different, audited comparison. |
| Table V / Figure 8: Triveni score 68.91 | Retained and expanded in Tables 8–9 and current Figure 7 | Filed numerical pairs, concept denominator, narrative counts, and weighted contributions are explained. Completeness is corrected from numerical-only language to all accepted concepts. |
| Table VI: 12 sector examples | Expanded into current Table 13: all 47 eligible sectors plus 25 pooled small groups | All 72 sectors remain in S2. The five-company rule is a presentation threshold, not a guarantee of statistical reliability. |
| Table VII: seven Pharmaceuticals examples | Restored as a narrative contrast and Supplementary Table S4 | Dabur 73.72 vs Kopran 32.38, spread 41.34; all seven component rows are preserved. The main within-sector demonstration remains financial, as requested. |
| Table VIII: eight year-wise trajectories | Restored to current Table 11 and full component file S3 | Mean 45.17 to 50.40, +5.23 points; six increases and two decreases. Dominant weighted shifts are arithmetic, not causal drivers. |
| Human rating correlation r=0.631, described as independently blind | Retained as r=0.6314, n=20, with CI 0.2683–0.8519 and unconfirmed blinding | The score-bearing source file does not establish that the rater was blind. |
| One-company 84 arithmetic checks: 61 pass, 2 fail, 21 not applicable | Not restored as an audited result | No supporting result artifact was located in the current approved audit/analysis files. The PDF alone does not establish the check definitions or the cause of the two mismatches. |
| Mean annual increase interpreted as confirmed real progress | Reframed as a descriptive available-case score change | Eight companies do not establish national progress or a causal change in sustainability outcomes. |
| “All three gaps directly resolved” and every service already validated | Replaced by scoped contribution and explicit validation boundaries | Claim–figure and assurance checks have no completed end-to-end accuracy estimate; API verification is a runtime case. |
| Broad future extensions | Dedicated final conclusion paragraph | Independent labels, blind ratings, train-only adaptation, stronger fact context, annexures/charts, better sector/applicability modelling, a balanced annual panel, and separately validated framework transfer. |

## Material restored versus intentionally left out

**Restored in the main narrative/table:** all eight annual trajectories, the +5.23-point available-case mean, the detailed ESAF score decomposition, and the Pharmaceuticals high/low contrast.

**Preserved in supplementary tables:** all 94 financial-company rows, all 72 sector rows, all 16 paired-year filing/component rows, and all seven Pharmaceuticals examples. No source CSV was overwritten.

**Intentionally excluded from final quantitative claims:** stale classifier results, unmatched adaptation/data-volume gains, reused-label detector tuning comparisons, experimental XGBoost importance, the legacy 393-row alignment result, and the unsupported one-company arithmetic-check total. Historical content is not automatically reusable as final validation.

## Files for review

- paper/main.tex: main manuscript entry point.
- paper/figures/architecture.tex: Figure 1 image wrapper and interpretation caption.
- paper/sections/05_results.tex: compact Tables 12–13, restored Table 11, and Pharmaceuticals narrative.
- paper/sections/06_discussion.tex: four retained subsections; former Section 6.5 removed.
- paper/sections/07_conclusion.tex: revised conclusion with final future-work paragraph.
- paper/supplementary/: S1–S4 complete result files and provenance notes.
- paper/revision/2026-10-22_result_compaction.json: exact descriptive derivations and source hashes.
- paper/revision/verification.json: current checks and compilation status.

No new experimental result was created during this revision.

## Literature-table pagination update

The comparative table now contains 14 selected modelling/disclosure studies. The Snorkel and general leakage-review rows were removed to eliminate the two-row overflow page; both sources remain discussed and cited in the literature prose. A temporary page-counter assertion during compilation of the actual main manuscript verified that Methodology starts on page 6. The assertion was then removed and the final main document compiled successfully.

## Plain-language revision

The abstract was reduced to 204 words and now highlights all seven workflow parts with only the main classifier agreement and human-score correlation. Detailed source results, confidence intervals, detector metrics, and sector values remain in the body. Narrative sentences, literature-table cells, figure captions, and table descriptions were rewritten in direct English. Required terms are explained at first use. Numerical table entries and equations are unchanged. In-place compilation checks confirmed the methodology still starts on page 6 and Tables 12 and 13 still fit on one page.

## Eight-request positive-tone revision

The current abstract is 176 words and highlights the seven-part pipeline. Repeated self-critical commentary and the dedicated Limitations headings were replaced with practical-use discussion. Material study conditions remain documented once where needed. The conclusion now opens future work with the requested level-wise sentence. The request-by-request audit is in eight_requested_changes_audit.md; requests 1, 5, and 6 are recorded as qualified reframing/consolidation rather than blanket removal. Metric tables and equations are unchanged.
