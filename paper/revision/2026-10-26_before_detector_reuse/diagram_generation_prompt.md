# Architecture illustration prompt — exact methodology titles

Create a publication-quality academic architecture diagram titled “GRASP: From BRSR Filings to Traceable Disclosure Analysis”.

Use a portrait 4:5 canvas at high resolution. Design for a full-width figure in a single-column journal, readable at 164 mm printed width. Use a white background, navy text, muted teal processing cards, pale blue data resources, and restrained amber review markers. Use consistent thin-line icons, flat vector styling, generous white space, and one clean sans-serif typeface. Avoid gradients, shadows, 3D objects, decorative leaves, stock illustrations, and ornamental graphics.

CRITICAL TITLE RULE
The seven module titles below must appear verbatim, including wording, case, and hyphens. Numbers belong in separate small circular badges. Allow a title to wrap onto two or three lines; never abbreviate or substitute a shorter title. The wording matches the Methodology subsection headings.

LAYOUT
Arrange three horizontal bands: “DATA PREPARATION AND MODEL TRAINING”, “DISCLOSURE ANALYSIS”, and “REPORTING AND ACCESS”. Use visually balanced workflow cards, not a table. Each card contains a line icon, exact module title, three short processing labels, and a clearly separated output strip.

Place a compact input element above the first band: document-stack icon, heading “BRSR XBRL filings”, and labels “Narratives”, “Numerical facts”, “Reporting context”. Connect the input to Module 1.

BAND A
Place Modules 1, 2 and 3 from left to right, with straight arrows 1 → 2 → 3. This is the dataset/training workflow. Below these cards, add a shared-data strip labelled “Shared filing data from Module 1”, with small labels “Narratives | Numerical facts | Context and assurance”. Connect Module 1 to that strip. Give the shared-data strip three separate short downward connections into Modules 4, 5 and 6.

BAND B
Place Modules 4, 5 and 6 as three parallel cards below the shared-data strip. Do not connect these cards sequentially. Module 5 additionally contains a small resource badge “BERT model · M3”; repeat that exact badge at the output of Module 3 to show the classifier dependency without a long crossing connector.

BAND C
Place Module 7 as one wide card below Modules 4–6. Draw three parallel vertical arrows from Modules 4–6 into three separate ports on Module 7. Beneath Module 7, show a compact output group with three line icons labelled “Company review”, “Sector comparison”, and “Evidence inspection”. Connect the group with one short central arrow.

EXACT MODULE CONTENT

MODULE 1
Icon: document entering a database.
Exact title: “Filing acquisition and structured storage”
Processing labels:
• Parse concepts and raw values
• Preserve units, periods and dimensions
• Link company, filing and fact records
Output strip: “Structured filing database”

MODULE 2
Icon: tagged document with organised data layers.
Exact title: “Narrative selection and weak-label construction”
Processing labels:
• Select and clean narratives
• Derive axis, concept and note labels
• Deduplicate and split companies by CIN
Output strip: “42,409 weak-labelled segments”

MODULE 3
Icon: neural-network chip.
Exact title: “Domain adaptation and principle classification”
Processing labels:
• Masked-language-model adaptation
• Nine-principle BERT fine-tuning
• Select and strictly verify the checkpoint
Output strip: “Recovered seed-99 BERT classifier”
Resource badge: “BERT model · M3”

MODULE 4
Icon: magnifying glass with a small review marker.
Exact title: “Vagueness and filing-consistency checks”
Processing labels:
• Lexicon hedging and MPNet similarity
• Claim–figure and assurance-gap checks
• Auxiliary omission check
Output strip: “Vagueness flags and review records”
Small scope label: “Evaluation covers the text-vagueness branch”

MODULE 5
Icon: compass connected to nine category markers.
Exact title: “Principle mapping and the zero-shot comparator”
Processing labels:
• Supervised principle probabilities
• MPNet definitions and anchors
• Compare ranked principle assignments
Output strip: “Principle summaries and ranked passages”
Resource badge: “BERT model · M3”

MODULE 6
Icon: gauge with four component bars.
Exact title: “Transparency Score and peer comparison”
Processing labels:
• Completeness 40% · Specificity 30%
• Clarity 20% · SDG breadth 10%
• Sector summaries and percentiles
Output strip: “Transparency Score and peer position”
Small scope label: “Fixed heuristic weights”

MODULE 7
Icon: server connected to a browser window.
Exact title: “Service layer and runtime traceability”
Processing labels:
• Company lookup and report access
• Expose method and recovered model path
• Return components and review evidence
Output strip: “Traceable company and sector reports”

CONNECTOR AND TYPOGRAPHY RULES
Use straight or orthogonal connectors in dedicated gutters. No intersections, diagonal shortcuts, overlapping labels, or arrows through boxes. Allow junction dots only for intentional shared-data branches. Keep arrowheads away from text and icons. Use identical icon sizes and card padding. Prioritise readable exact titles; widen a card or increase height instead of shrinking text. Preserve clear visual hierarchy between band labels, module titles, processing labels, and output strips.

SCIENTIFIC ACCURACY
Modules 4, 5 and 6 are parallel analyses. Principle probabilities and numerical review flags are separate report outputs, rather than direct terms in the Transparency Score formula. The recovered classifier is specifically used by Module 5. Numerical and assurance checks remain review heuristics. Include no invented accuracy, greenwashing verdict, legal-compliance badge, independent-human-validation badge, extra model, or additional module. Keep all seven titles exact. Use no personal pronouns.
