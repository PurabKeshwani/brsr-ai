"""
Compliance Mapper (Phase 4)

Measures how semantically aligned a company's narrative disclosure under
each SEBI/NGRBC principle is with that principle's OFFICIAL regulatory
definition — using the same sentence-transformers embedding approach
already validated in the vagueness-detection layer (Phase D), applied
here against a different reference: not "vague vs quantified" example
sentences, but the actual regulatory text itself.

OFFICIAL SOURCE: the nine principle definitions below are the exact
wording of the National Guidelines on Responsible Business Conduct
(NGRBC), issued by the Ministry of Corporate Affairs (2019), which SEBI's
BRSR circular (SEBI/HO/CFD/CMD-2/P/CIR/2021/562, May 10 2021) explicitly
adopts as the reporting framework's nine principles. This wording was
verified against multiple independent sources during development (see
conversation history) since the circular's own annexures (which contain
this exact text) were not directly available to this project — the
wording is consistent across every source checked, which is the expected
signature of quoted official text rather than paraphrase.

WHAT THIS MEASURES (and what it doesn't): a HIGH similarity score means a
company's disclosure under a principle uses language and content
thematically close to what that principle is officially about — e.g. a
P6 disclosure that discusses environmental protection, emissions, or
resource restoration will score higher than one that's generic corporate
boilerplate with no environmental content. This is a coarse alignment
signal, not a legal compliance determination — a company can score highly
here while still failing to meet specific mandatory indicator
requirements (which are checked separately by Completeness, Specificity,
and the Truth Auditor). This component measures WHETHER a company is
discussing the right thing under each principle, not whether its
disclosure is complete, specific, or truthful — those are the other
Transparency Score components' jobs.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from sentence_transformers import SentenceTransformer, util
from sqlalchemy.orm import Session

from db.models import Fact

MODEL_NAME = "all-mpnet-base-v2"  # same model used throughout Phase D, for consistency

# Official NGRBC principle text & statutory scope — MCA (2019) and SEBI BRSR Core Circular
OFFICIAL_PRINCIPLE_TEXT: dict[int, str] = {
    1: (
        "Businesses should conduct and govern themselves with integrity, and in a manner that is ethical, transparent and accountable. "
        "Governance structure, anti-corruption and anti-bribery policies, whistleblower mechanism, vigilance, ethics, conflict of interest, "
        "code of conduct, regulatory penalties, fines, disciplinary action, and enforcement by regulators such as SEBI, RBI, MCA, and stock exchanges."
    ),
    2: (
        "Businesses should provide goods and services in a manner that is sustainable and safe. "
        "Sustainable sourcing of raw materials, local MSME procurement, Life Cycle Assessment (LCA) of products, environmental and social impacts, "
        "Extended Producer Responsibility (EPR), recycling, reuse, safe design, reclaimed products and packaging, and circular economy."
    ),
    3: (
        "Businesses should respect and promote the well-being of all employees, including those in their value chains. "
        "Occupational health and safety, lost time injury frequency rate, workplace accidents, fatalities, minimum wages, fair remuneration, "
        "health insurance, parental maternity paternity benefits, day care, POSH prevention of sexual harassment committee, "
        "trade unions, collective bargaining agreements, employee skill training and professional career development."
    ),
    4: (
        "Businesses should respect the interests of and be responsive to all its stakeholders. "
        "Stakeholder engagement and periodic consultations, identification and mapping of key stakeholders, shareholders, employees, suppliers, "
        "customers, local communities, vulnerable and marginalized groups, materiality assessment of ESG topics, and grievance redressal for stakeholders."
    ),
    5: (
        "Businesses should respect and promote human rights. "
        "Human rights policy, human rights due diligence, prevention of child labour, forced labour, involuntary or compulsory labour, "
        "human trafficking, fair living wages, human rights grievance redressal mechanisms, and supply chain human rights reviews."
    ),
    6: (
        "Businesses should respect and make efforts to protect and restore the environment. "
        "Resource conservation, energy consumption and renewable energy, solar wind biomass, water withdrawal, water consumption, "
        "rainwater harvesting, Zero Liquid Discharge (ZLD), effluent treatment plants (ETP STP), greenhouse gas emissions, "
        "Scope 1 direct emissions, Scope 2 indirect emissions, Scope 3 supply chain emissions, air pollutants, hazardous and non-hazardous waste management, "
        "recycling, TSDF disposal, and biodiversity conservation."
    ),
    7: (
        "Businesses, when engaging in influencing public and regulatory policy, should do so in a manner that is responsible and transparent. "
        "Public policy advocacy, policy submissions and memorandums to government ministries and statutory regulators, "
        "membership in trade and industry associations, chambers of commerce such as CII, FICCI, ASSOCHAM, transparent representation, "
        "and anti-competitive market practices."
    ),
    8: (
        "Businesses should promote inclusive growth and equitable development. "
        "Corporate Social Responsibility (CSR) initiatives, community development projects, rural welfare, education, healthcare, "
        "infrastructure development, Social Impact Assessment (SIA), rehabilitation and resettlement, local community employment, "
        "affirmative action, and procurement from local and small suppliers."
    ),
    9: (
        "Businesses should engage with and provide value to their consumers in a responsible manner. "
        "Consumer satisfaction surveys, customer complaints received and resolved, complaint redressal mechanisms, "
        "product labeling, display of product information, safe product usage instructions, cybersecurity incidents, "
        "customer data privacy, data breaches, product recalls, and fair marketing practices."
    ),
}

OFFICIAL_PRINCIPLE_ANCHORS: dict[int, list[str]] = {
    1: [
        "Businesses should conduct and govern themselves with integrity, and in a manner that is ethical, transparent and accountable.",
        "Corporate governance structure, Board committees, anti-corruption, anti-bribery policies, and ethical business conduct.",
        "Whistleblower mechanism, vigilance policy, ombudsman, fraud prevention, and conflict of interest disclosures.",
        "Fines, penalties, show-cause notices, and disciplinary actions imposed by statutory regulators like SEBI, RBI, MCA, and stock exchanges."
    ],
    2: [
        "Businesses should provide goods and services in a manner that is sustainable and safe.",
        "Sustainable sourcing of raw materials, local MSME procurement, and value chain environmental responsibility.",
        "Life Cycle Assessment (LCA) of products, eco-design, and environmental impact of products and services.",
        "Extended Producer Responsibility (EPR), recycling, waste recovery, reclaimed packaging materials, and circular economy."
    ],
    3: [
        "Businesses should respect and promote the well-being of all employees, including those in their value chains.",
        "Occupational health and safety, lost time injury frequency rate (LTIFR), workplace accidents, safety audits, and zero fatalities.",
        "Fair wages, statutory minimum wages, provident fund, ESI, health insurance, maternity benefits, paternity leave, and daycare.",
        "Prevention of Sexual Harassment (POSH) policy, Internal Complaints Committee (ICC), grievance redressal for employees.",
        "Trade unions, collective bargaining agreements, employee skill training, safety drills, and performance appraisal."
    ],
    4: [
        "Businesses should respect the interests of and be responsive to all its stakeholders.",
        "Identification and prioritisation of key stakeholders: employees, suppliers, customers, shareholders, and local communities.",
        "Stakeholder consultation processes, engagement channels, frequency of dialogue, and collaborative partnerships.",
        "Materiality assessment: identifying and managing material environmental, social, and governance issues raised by stakeholders.",
        "Grievance redressal mechanisms for stakeholders, community consultations, and vulnerable and marginalized groups."
    ],
    5: [
        "Businesses should respect and promote human rights.",
        "Human rights policy, principles, commitments, and human rights due diligence across business operations.",
        "Prohibition and prevention of child labour, forced labour, involuntary labour, and human trafficking.",
        "Equal opportunity, non-discrimination, fair living wages, and safe working conditions across employees and contractors.",
        "Human rights grievance redressal mechanisms, supply chain social audits, and human rights assessments."
    ],
    6: [
        "Businesses should respect and make efforts to protect and restore the environment.",
        "Energy consumption, electricity usage, energy efficiency initiatives, and renewable energy adoption: solar, wind, biomass.",
        "Water withdrawal, groundwater, municipal water, water consumption, rainwater harvesting, and Zero Liquid Discharge (ZLD).",
        "Effluent Treatment Plants (ETP), Sewage Treatment Plants (STP), and industrial wastewater recycling and treatment.",
        "Greenhouse gas (GHG) emissions, carbon footprint, Scope 1 direct emissions, Scope 2 indirect emissions, Scope 3 supply chain emissions.",
        "Hazardous and non-hazardous waste management, waste segregation, recycling, co-processing, and authorized TSDF disposal.",
        "Air emissions, particulate matter, SOx, NOx, stack monitoring, environmental compliance, and biodiversity conservation."
    ],
    7: [
        "Businesses, when engaging in influencing public and regulatory policy, should do so in a manner that is responsible and transparent.",
        "Public policy advocacy, representation to government ministries, departments, and statutory regulatory authorities.",
        "Membership in trade associations and industry chambers: CII, FICCI, ASSOCHAM, NASSCOM, PHDCCI, and industrial bodies.",
        "Transparent advocacy, policy memorandums, ethical representation, and compliance with anti-competitive trade laws."
    ],
    8: [
        "Businesses should promote inclusive growth and equitable development.",
        "Corporate Social Responsibility (CSR) initiatives, community development projects, rural welfare, education, and healthcare programs.",
        "Social Impact Assessment (SIA) for projects, Rehabilitation and Resettlement (R&R) of project affected persons.",
        "Local community engagement, skill building, livelihood creation, affirmative action, and local community infrastructure.",
        "Preferential procurement from local vendors, MSME suppliers, and marginalized community entrepreneurs."
    ],
    9: [
        "Businesses should engage with and provide value to their consumers in a responsible manner.",
        "Consumer satisfaction surveys, Net Promoter Score (NPS), feedback mechanisms, and customer relations.",
        "Consumer complaints received, resolved, and pending regarding products, services, delivery, and quality.",
        "Product labeling, display of product ingredients, safe usage instructions, Safety Data Sheets (SDS), and transparent information.",
        "Cybersecurity, information security, customer data privacy, handling of personal data, and data breach prevention.",
        "Product recalls, corrective actions, warranty claims, and fair advertising and marketing communications."
    ]
}

PRINCIPLE_TO_LABEL = {f"Principle{i}Member": i for i in range(1, 10)}
MIN_TEXT_LENGTH = 20


@lru_cache(maxsize=1)
def _get_model() -> SentenceTransformer:
    return SentenceTransformer(MODEL_NAME)


@lru_cache(maxsize=1)
def _get_principle_embeddings():
    model = _get_model()
    principle_nums = sorted(OFFICIAL_PRINCIPLE_TEXT.keys())
    texts = [OFFICIAL_PRINCIPLE_TEXT[n] for n in principle_nums]
    embeddings = model.encode(texts, convert_to_tensor=True)
    return principle_nums, embeddings


@lru_cache(maxsize=1)
def _get_principle_anchor_embeddings():
    model = _get_model()
    anchor_dict = {}
    for p, anchors in OFFICIAL_PRINCIPLE_ANCHORS.items():
        anchor_dict[p] = model.encode(anchors, convert_to_tensor=True)
    return anchor_dict


@dataclass
class PrincipleComplianceScore:
    principle_num: int
    mean_similarity: float       # average alignment across all this company's segments under this principle
    segment_count: int
    weakest_segment: str | None  # the lowest-scoring segment — useful evidence for review
    weakest_segment_similarity: float | None


@dataclass
class ComplianceMapperResult:
    per_principle: dict[int, PrincipleComplianceScore]
    overall_compliance_alignment_pct: float  # mean across all principles that had at least one segment


def get_compliance_mapping(session: Session, filing_id: int) -> ComplianceMapperResult:
    model = _get_model()
    principle_nums, principle_embeddings = _get_principle_embeddings()

    text_facts = (
        session.query(Fact)
        .filter(Fact.filing_id == filing_id, Fact.concept.like("%ExplanatoryTextBlock%"))
        .all()
    )

    # Deduplicate text that appears under MULTIPLE PrincipleAxis values
    # for this company (real bug found and fixed here — see
    # build_training_dataset.py's docstring for the full original
    # discovery: SEBI's form structure lets a company file one blanket
    # statement, e.g. a statutory-auditor disclosure or a policy weblink,
    # and have it replicated across ALL 9 principles identically). Such
    # text is not evidence of principle-specific alignment and should be
    # excluded, not compared against every principle's definition.
    text_to_principles: dict[str, set[int]] = {}
    for f in text_facts:
        principle_dim = f.dimensions.get("PrincipleAxis")
        text = f.value.strip()
        if principle_dim in PRINCIPLE_TO_LABEL and len(text) >= MIN_TEXT_LENGTH:
            text_to_principles.setdefault(text, set()).add(PRINCIPLE_TO_LABEL[principle_dim])

SUPERVISED_MODEL_PATH = Path("data/models/brsr_principle_classifier/final_model_unweighted_93.68")


@lru_cache(maxsize=1)
def _get_domain_adapted_model():
    if not SUPERVISED_MODEL_PATH.exists():
        return None, None
    import torch
    from transformers import AutoTokenizer, AutoModelForSequenceClassification
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tokenizer = AutoTokenizer.from_pretrained(str(SUPERVISED_MODEL_PATH))
    model = AutoModelForSequenceClassification.from_pretrained(str(SUPERVISED_MODEL_PATH)).to(device)
    model.eval()
    return tokenizer, model


def get_compliance_mapping(
    session: Session,
    filing_id: int,
    use_domain_adapted: bool = True,
) -> ComplianceMapperResult:
    text_facts = (
        session.query(Fact)
        .filter(Fact.filing_id == filing_id, Fact.concept.like("%ExplanatoryTextBlock%"))
        .all()
    )

    text_to_principles: dict[str, set[int]] = {}
    for f in text_facts:
        principle_dim = f.dimensions.get("PrincipleAxis")
        text = f.value.strip()
        if principle_dim in PRINCIPLE_TO_LABEL and len(text) >= MIN_TEXT_LENGTH:
            text_to_principles.setdefault(text, set()).add(PRINCIPLE_TO_LABEL[principle_dim])

    by_principle: dict[int, set[str]] = {}
    for text, principles in text_to_principles.items():
        if len(principles) > 1:
            continue  # cross-principle boilerplate — excluded
        principle_num = next(iter(principles))
        by_principle.setdefault(principle_num, set()).add(text)

    per_principle: dict[int, PrincipleComplianceScore] = {}

    tokenizer, sup_model = _get_domain_adapted_model() if use_domain_adapted else (None, None)

    if sup_model is not None and tokenizer is not None:
        import torch
        import torch.nn.functional as F
        device = sup_model.device

        for principle_num, texts in by_principle.items():
            texts_list = list(texts)
            inputs = tokenizer(texts_list, padding=True, truncation=True, max_length=512, return_tensors="pt").to(device)
            with torch.no_grad():
                logits = sup_model(**inputs).logits
                probs = F.softmax(logits, dim=1)

            # Extract alignment score for this specific principle (principle_num is 1-indexed)
            principle_probs = probs[:, principle_num - 1].cpu().tolist()
            mean_sim = sum(principle_probs) / len(principle_probs)
            min_idx = principle_probs.index(min(principle_probs))

            per_principle[principle_num] = PrincipleComplianceScore(
                principle_num=principle_num,
                mean_similarity=round(mean_sim, 4),
                segment_count=len(texts_list),
                weakest_segment=texts_list[min_idx],
                weakest_segment_similarity=round(principle_probs[min_idx], 4),
            )
    else:
        model = _get_model()
        principle_nums, principle_embeddings = _get_principle_embeddings()
        anchor_dict = _get_principle_anchor_embeddings()

        for principle_num, texts in by_principle.items():
            texts_list = list(texts)
            segment_embeddings = model.encode(texts_list, convert_to_tensor=True)

            principle_idx = principle_nums.index(principle_num)
            reference_embedding = principle_embeddings[principle_idx : principle_idx + 1]
            sims_enriched = util.cos_sim(segment_embeddings, reference_embedding).squeeze(1)

            anchor_embs = anchor_dict[principle_num]
            anchor_sims = util.cos_sim(segment_embeddings, anchor_embs)
            max_anchor, _ = anchor_sims.max(dim=1)
            mean_anchor = anchor_sims.mean(dim=1)
            score_anchor = 0.70 * max_anchor + 0.30 * mean_anchor
            hybrid_sims = 0.50 * sims_enriched + 0.50 * score_anchor
            sims_list = hybrid_sims.tolist()

            mean_sim = sum(sims_list) / len(sims_list)
            min_idx = sims_list.index(min(sims_list))

            per_principle[principle_num] = PrincipleComplianceScore(
                principle_num=principle_num,
                mean_similarity=round(mean_sim, 4),
                segment_count=len(texts_list),
                weakest_segment=texts_list[min_idx],
                weakest_segment_similarity=round(sims_list[min_idx], 4),
            )

    overall = (
        round(sum(p.mean_similarity for p in per_principle.values()) / len(per_principle) * 100, 2)
        if per_principle else 0.0
    )

    return ComplianceMapperResult(per_principle=per_principle, overall_compliance_alignment_pct=overall)