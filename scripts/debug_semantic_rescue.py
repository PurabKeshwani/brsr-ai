"""
Diagnostic — shows exactly which sentence "rescued" a paragraph from being
flagged vague, for the two new false-negatives introduced by the
sentence-level fix. Needed to judge whether the min/max-per-sentence
scoring strategy needs adjusting, rather than guessing.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from analysis.vagueness_semantic import analyze_semantic_vagueness

TEXTS = {
    "Gujarat Ambuja (stakeholder)": (
        "GAEL recognises the importance of engaging with its key stakeholders to create long-term value and "
        "support sustainable business practices. \nStakeholders are identified and prioritised based on their "
        "influence on the Company's operations and the impact of the Company's activities on them. The stakeholder "
        "identification process includes stakeholder mapping, periodic consultations, and ongoing engagement to "
        "understand their expectations, concerns, and material issues. Key stakeholder groups include employees, "
        "customers (downstream value chain), suppliers (upstream value chain), shareholders, government and "
        "regulatory authorities, and communities surrounding its operations.\nThe Company engages with these "
        "stakeholder groups through various channels, including community consultations, supplier interactions, "
        "customer and employee feedback, investor and analyst interactions, and regulatory engagements. Inputs "
        "received through these engagements support the Company's decision-making, policy development, and "
        "sustainability initiatives."
    ),
    "Poly Medicure (materiality)": (
        "Notes for Overview of the entity's material responsible business conduct issues.\n"
        "- Polymed conducted a materiality assessment through a structured stakeholder engagement process to "
        "identify and prioritize the material responsible business conduct and sustainability topics most relevant "
        "to its business and stakeholders. The identified material topics guide the Company's sustainability "
        "strategy, enabling effective management of key risks and opportunities while supporting long-term value "
        "creation and responsible business growth."
    ),
}

for label, text in TEXTS.items():
    result = analyze_semantic_vagueness(text)
    print(f"\n=== {label} ===")
    print(f"is_flagged_vague: {result.is_flagged_vague}")
    print(f"max_similarity_to_vague: {result.max_similarity_to_vague}")
    print(f"max_similarity_to_quantified: {result.max_similarity_to_quantified}")
    print(f"'Rescuing' sentence: {result.most_specific_sentence}")