# Paper table and language revision audit

Date: 2 November 2026
Main document: paper/main.tex

## Requested changes

| Request | Change | Verification |
|---|---|---|
| Page-27 table issue | Restored the all-sector table's 47 missing rows. A placeholder comment had replaced the rows. Kept the financial summary before the all-sector subsection and the full sector table before the following interpretation. | 47 eligible sectors contain 1,109 companies; 25 pooled sectors contain 55 companies; total 1,164. |
| Every cited table must be available | Included supplementary tables S1–S4 in the same manuscript and replaced manually written S references with LaTeX labels. Added explicit introductions for Tables 3 and 9. | All 13 main tables and four supplementary tables have at least one text reference. No unresolved or duplicate labels. |
| Literature Review should discuss GRASP only after the review | Removed interspersed GRASP comparisons. The GRASP synthesis now follows the related-work narrative and literature table. | First GRASP occurrence in the Literature Review follows the end of the review table. |
| Inference drawn should state takeaways | Rewrote all 14 inference cells as conclusions drawn from the reviewed findings, rather than instructions to implement a component. | Existing citation keys and study scope retained. |
| More model-development detail | Explained base uncased BERT, unlabelled masked-language adaptation, nine-output supervised training, tokenisation, truncation and padding, weighted loss, validation selection, and checkpoint recovery. | Training settings checked against the audited company-level trainer and Stage 3 audit. |
| Rename Design choices | Replaced the heading with Research findings and motivation and placed the synthesis after the review table. | Heading and section order checked. |
| Abstract flow and clarity | Rewrote the abstract in order: review problem, report collection, weak-label creation, adapted BERT, review checks, principle summaries, score and service, principal results. | 93.00% label agreement and r=0.6314 retained with evaluation counts; no XBRL in the abstract. |

## Supplementary tables included in the PDF

| Table | Contents | Records | Source CSV |
|---|---|---:|---|
| S1 | Full financial-company results, reconstructed report end date, components, score, sector percentile and scoring text-segment count | 94 companies | table_S1_financial_companies.csv |
| S2 | Full sector summary, including medians and small-sector groups | 72 sectors | table_S2_all_sectors.csv |
| S3 | Report identifiers, financial-year labels and every score component for paired-year companies | 16 reports from 8 companies | table_S3_paired_year_components.csv |
| S4 | Four highest and three lowest pharmaceutical-company examples with components and percentiles | 7 companies | table_S4_pharmaceutical_examples.csv |

The CSV sources remain unchanged. Display values use the source precision rounded to two decimal places, with percentiles shown to one decimal place. Company names are retained; the explanatory Sudarshan alias is omitted from the paired table, and the sector abbreviation IT is expanded to Information Technology.

## Additional consistency fixes

- Removed the restored Discussion and Practical Use section from the active manuscript and removed the roadmap reference. The source file remains available outside the compiled document.
- Shortened the Methodology opening so the overview and diagram satisfy the existing one-page layout check. The Figure 1 caption states the purpose of the workflow.
- Restored the exact future-work opening: This work can be extended using multiple levels.
- Removed the prohibited personal pronouns from active manuscript prose and corrected the repeated classifier-section reference.
- Tables 12 and 13 have caption-and-body height checks that stop compilation if either table exceeds one text page. Both checks pass.

## Verification outcome

- Built-in desktop compilation: **SUCCESS** for the saved paper/main.tex.
- Main tables: **13**; supplementary tables: **4**; total **17**.
- Missing input files: **0**.
- Unresolved section, figure, equation or table references: **0**.
- Duplicate labels: **0**.
- Missing bibliography keys: **0**.
- Prohibited pronoun/Project-word matches in active manuscript prose: **0**.
- Financial-band counts and mean scores match the saved S1 data: 11/62.39, 35/54.77, 26/45.22, 22/34.05.
- No ML training, inference or new performance evaluation was run. Approved metrics and evidence conditions were retained.

Layout verification in this pass uses the compiler and the source-level one-page checks. A page-by-page visual inspection of the compiled PDF was not performed. Additional explanations and supplementary tables change pagination, so the previous page 27 need not keep the same content. The existing root GRASP_Journal.pdf was not overwritten; the editor preview is generated from the revised source.

The source snapshot before revision is saved under revision/2026-11-02_before_table_and_language_fixes/.
