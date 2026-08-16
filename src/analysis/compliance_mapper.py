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

from sentence_transformers import SentenceTransformer, util
from sqlalchemy.orm import Session

from db.models import Fact

MODEL_NAME = "all-mpnet-base-v2"  # same model used throughout Phase D, for consistency

# Official NGRBC principle text — see module docstring for sourcing.
OFFICIAL_PRINCIPLE_TEXT: dict[int, str] = {
    1: "Businesses should conduct and govern themselves with integrity, and in a manner that is ethical, transparent and accountable.",
    2: "Businesses should provide goods and services in a manner that is sustainable and safe.",
    3: "Businesses should respect and promote the well-being of all employees, including those in their value chains.",
    4: "Businesses should respect the interests of and be responsive to all its stakeholders.",
    5: "Businesses should respect and promote human rights.",
    6: "Businesses should respect and make efforts to protect and restore the environment.",
    7: "Businesses, when engaging in influencing public and regulatory policy, should do so in a manner that is responsible and transparent.",
    8: "Businesses should promote inclusive growth and equitable development.",
    9: "Businesses should engage with and provide value to their consumers in a responsible manner.",
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

    by_principle: dict[int, set[str]] = {}
    for text, principles in text_to_principles.items():
        if len(principles) > 1:
            continue  # cross-principle boilerplate — excluded
        principle_num = next(iter(principles))
        by_principle.setdefault(principle_num, set()).add(text)

    per_principle: dict[int, PrincipleComplianceScore] = {}

    for principle_num, texts in by_principle.items():
        texts_list = list(texts)
        segment_embeddings = model.encode(texts_list, convert_to_tensor=True)

        principle_idx = principle_nums.index(principle_num)
        reference_embedding = principle_embeddings[principle_idx : principle_idx + 1]

        sims = util.cos_sim(segment_embeddings, reference_embedding).squeeze(1)
        sims_list = sims.tolist()

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