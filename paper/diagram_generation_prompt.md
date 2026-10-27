# GRASP diagram: detector reuse for Clarity

Date: 2026-10-26
Mode: built-in image_gen; edit using the existing paper diagram as reference.
Edit target: paper/figures/grasp_pipeline.png
Original preserved: paper/revision/2026-10-26_before_detector_reuse/grasp_pipeline.png
Final paper asset: paper/figures/grasp_pipeline.png

## Exact generation prompt

Use case: precise-object-edit / infographic-diagram.
Asset type: a publication-quality research-paper architecture figure, high-resolution portrait raster on an opaque white background.
Input image 1 is the EDIT TARGET and the visual style reference. Rebuild this exact GRASP architecture as a clean professional diagram with the SAME seven numbered modules, SAME exact module titles, SAME simple outlined icons, pale teal panels, dark navy strokes and typography. The requested change is one essential dependency: module 6 reuses the language vagueness detector defined in module 4 to calculate Clarity, weighted 20% in the Transparency Score.

CRITICAL SCIENTIFIC CONTENT:
The solid main connections are exactly: input -> 1; 1 -> 2; 2 -> 3; 3 -> 5; 1 -> 4; 1 -> 6; 4 -> 7; 5 -> 7; 6 -> 7; 7 -> output.
Add one DASHED dark-teal directed connection 4 -> 6. Its two-line label must read exactly "Detector reuse for" and "Clarity (20%)". This refers ONLY to reuse of the language vagueness detector, not all numerical/assurance flags entering the score. Do NOT add 4 -> 5, 3 -> 6 or any other connections. Do NOT imply the classifier probabilities or all review flags are score components.

LAYOUT TO AVOID ARROW CROSSINGS:
Keep input and module 1 centred at the top. Arrange the rest as two clean vertical lanes with ample whitespace: on the RIGHT, stack module 2, module 3 and module 5 in that order; on the LEFT, module 4 above module 6. Put module 7 centred below both lanes, and the final output below 7. This makes modules 4 and 6 vertically adjacent so their dashed dependency can be a short clearly labelled downward arrow.
Route the direct module 1 -> 6 solid database-input connection along the FAR LEFT outside edge, entering the LEFT edge of module 6; it must bypass module 4 without touching it.
Route module 1 -> 4 to the TOP of module 4. Route 1 -> 2 into module 2 at the top. Keep the solid 2 -> 3 -> 5 chain in the right lane. Give module 4 a SEPARATE solid result connection leaving its RIGHT edge, travelling down the empty CENTRAL corridor, then joining the result collection bus below modules 5 and 6. Modules 5 and 6 also feed that bus; show a single intentional junction into 7.
No edges may run through text or boxes; no unconnected edges may cross or overlap; no ambiguous junctions. A genuine shared results bus with a visible junction is allowed. Make generous spacing, aligned panels, balanced readable typography. Preserve the portrait aspect ratio near 4:5 so this remains legible on a journal page.

EXACT TEXT, render verbatim:
Input: "BRSR XBRL filings"
1: "Filing acquisition and structured storage"
2: "Narrative selection and weak-label construction"
3: "Domain adaptation and principle classification"
4: "Vagueness and filing-consistency checks"
5: "Principle mapping and the zero-shot comparator"
6: "Transparency Score and peer comparison"
7: "Service layer and runtime traceability"
Output: "Company and sector reports"
Small labels on the direct 1 -> 2, 1 -> 4 and 1 -> 6 edges: "Filing data".
On 3 -> 5: "Trained model".
New dashed 4 -> 6 dependency label: "Detector reuse for" / "Clarity (20%)".
Minimal two-item legend, with line samples, in the bottom margin: "Data / model / results" for a solid line, "Detector reuse" for a dashed line.

CONSTRAINTS: Preserve the seven modules and numbering exactly, no extra modules, no prose paragraphs, no formulas other than the requested 20% annotation, no decorative stock images, no watermark, no shadows or 3D, no overlapping arrows, no spelling errors. Icons remain consistent black outline icons appropriate to documents/database, labels, BERT/AI chip, review/magnifier, principle network, score/comparison, and API/server. Design should read as a restrained scientific architecture diagram, not a poster.
