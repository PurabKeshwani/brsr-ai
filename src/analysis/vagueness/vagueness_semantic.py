"""
Greenwashing Vagueness Detection — Semantic Layer (Phase D2)

Complements vagueness_lexicon.py (exact-phrase hedging detection) with
embedding-based similarity: scores each sentence in a segment against a
curated pool of known-vague statements and a curated pool of
known-quantified/specific statements, then flags the segment based on its
MOST SPECIFIC sentence — i.e. a segment is only flagged if even its best
sentence still reads as vague. This catches paraphrased hedging language
that doesn't use any of the lexicon's literal phrases, while avoiding one
bad opening line contaminating an otherwise well-evidenced paragraph.

Uses sentence-transformers 'all-mpnet-base-v2' as specified in the
project report's methodology section (5.3.3).

DESIGN HISTORY — two bugs found, one fix reverted after evidence showed
it regressed overall performance (see conversation history for full
detail; both real, both measured against the same 30-sample human-labeled
validation set):

1. FIXED: whole-paragraph embedding let one generic opening sentence drag
   the entire paragraph toward the vague pool. Fixed by sentence-splitting
   and using the single most-specific sentence's score, below.

2. ATTEMPTED AND REVERTED: a stricter two-condition rule (flag if ANY
   sentence is vague AND NO sentence is specific) was tried to fix two
   remaining false negatives (paragraphs with genuinely vague content but
   no single "rescuing" specific sentence). It fixed those two cases but
   dropped precision from 0.846 to 0.619 (F1 0.846 -> 0.765) by
   introducing 6 new false positives — many multi-sentence paragraphs
   contain at least one generically-toned connector sentence (e.g. "aimed
   at enhancing customer satisfaction") that superficially resembles the
   vague pool without being genuine hedging, and the quantified pool
   (built from numeric-metric example sentences) under-matches
   named-entity evidence (ISO/TSDF/committee names) stylistically. Net
   effect was worse overall, so this version was kept instead. The two
   known false negatives (see paper's limitations section) are the
   documented cost of this choice.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

from sentence_transformers import SentenceTransformer, util

MODEL_NAME = "all-mpnet-base-v2"

VAGUE_REFERENCE_EXAMPLES = [
    "We are committed to continuously improving our sustainability performance over time.",
    "The company strives to achieve excellence in all aspects of environmental stewardship.",
    "We aim to enhance our practices going forward through ongoing efforts.",
    "Significant progress has been made in strengthening our governance framework.",
    "The organisation is dedicated to fostering a culture of responsibility across all operations.",
    "We endeavour to align our practices with global sustainability standards where feasible.",
    "Considerable efforts have been undertaken to promote inclusive growth in the communities we serve.",
    "The company remains focused on driving meaningful change through comprehensive initiatives.",
    "We are working towards building a more sustainable future for all our stakeholders.",
    "Our approach reflects a robust and holistic commitment to responsible business conduct.",
]

QUANTIFIED_REFERENCE_EXAMPLES = [
    "The company reduced its Scope 1 emissions by 20.58% compared to the previous financial year.",
    "A total of 1,282 male and 1,206 female employees were reported as permanent staff as of FY26.",
    "Water withdrawal increased from 17,089.56 kilolitres to 17,616.66 kilolitres, a 3.08% rise.",
    "The company achieved ISO 14001:2015 certification for its Mumbai and Navi Mumbai facilities.",
    "Total waste generated decreased from 40.65 tonnes to 4.58 tonnes during the reporting period.",
    "97.9% of employees completed the mandatory training on health and safety measures in FY26.",
    "The board comprises 8 directors, of whom 2 (25%) are women.",
    "Energy consumption from renewable sources rose to 27.78% of total consumption in FY26.",
    "The company reported zero fatalities and zero high-consequence injuries during the year.",
    "Minimum wages were paid to 100% of permanent employees and workers as verified by internal audit.",
    "The company established an Internal Complaints Committee and Whistleblower mechanism under the POSH Act for formal grievance redressal.",
    "The company operates an on-site Zero Liquid Discharge (ZLD) facility and Effluent Treatment Plant (ETP) for total wastewater recycling.",
    "The manufacturing facilities are fully certified under ISO 14001:2015 and ISO 45001:2018 for environmental and occupational health standards.",
    "The reported ESG data underwent independent limited assurance by a statutory auditor in accordance with ISAE 3000.",
    "The CSR Committee approved and allocated funds across verified community development projects benefiting local stakeholders.",
    "The company maintains a formal Code of Conduct and Anti-Bribery policy overseen by the Audit Committee of the Board.",
]


def _split_sentences(text: str) -> list[str]:
    """Simple sentence splitter — consistent with the approach used in
    analysis/greenwashing.py for the same reason (BRSR prose is generally
    straightforward; this is sufficient to separate a generic opening
    line from specific, fact-bearing sentences that follow it)."""
    raw = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [s.strip() for s in raw if len(s.strip()) > 15]  # drop fragments too short to carry meaning


@lru_cache(maxsize=1)
def _get_model() -> SentenceTransformer:
    return SentenceTransformer(MODEL_NAME)


@lru_cache(maxsize=1)
def _get_reference_embeddings():
    model = _get_model()
    vague_emb = model.encode(VAGUE_REFERENCE_EXAMPLES, convert_to_tensor=True)
    quantified_emb = model.encode(QUANTIFIED_REFERENCE_EXAMPLES, convert_to_tensor=True)
    return vague_emb, quantified_emb


@dataclass
class SemanticVaguenessResult:
    text: str
    max_similarity_to_vague: float
    max_similarity_to_quantified: float
    most_specific_sentence: str  # the sentence that most reads as quantified/specific — evidence for why the paragraph wasn't flagged

    @property
    def is_flagged_vague(self) -> bool:
        return (
            self.max_similarity_to_vague >= 0.42
            and self.max_similarity_to_vague > self.max_similarity_to_quantified
        )


def analyze_semantic_vagueness(text: str) -> SemanticVaguenessResult:
    model = _get_model()
    vague_emb, quantified_emb = _get_reference_embeddings()

    sentences = _split_sentences(text)
    if not sentences:
        sentences = [text]  # fallback for text with no clear sentence boundaries

    sentence_embs = model.encode(sentences, convert_to_tensor=True)

    vague_sims_per_sentence = util.cos_sim(sentence_embs, vague_emb).max(dim=1).values
    quantified_sims_per_sentence = util.cos_sim(sentence_embs, quantified_emb).max(dim=1).values

    # Score the paragraph by its MOST specific sentence (highest
    # quantified-minus-vague margin) — a paragraph is only flagged if
    # even its best sentence still reads as vague relative to specific.
    specificity_margin = quantified_sims_per_sentence - vague_sims_per_sentence
    most_specific_idx = int(specificity_margin.argmax())

    return SemanticVaguenessResult(
        text=text,
        max_similarity_to_vague=round(float(vague_sims_per_sentence[most_specific_idx]), 4),
        max_similarity_to_quantified=round(float(quantified_sims_per_sentence[most_specific_idx]), 4),
        most_specific_sentence=sentences[most_specific_idx],
    )