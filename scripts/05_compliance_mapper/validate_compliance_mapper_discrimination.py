"""
Validity check for compliance_mapper.py — tests whether a company's text
under principle P actually scores HIGHEST against P's own official
definition, compared to the other 8 principles' definitions.

Tests EVERY deduplicated segment per principle (not a single arbitrary
sample — an earlier version used list(texts)[0], which happened to
repeatedly land on non-informative weblink/URL text since Python set
iteration order is unpredictable, giving a misleadingly weak result that
didn't reflect how the real get_compliance_mapping function actually
behaves, since that function averages across ALL segments per principle
rather than picking one).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from analysis.compliance.compliance_mapper import (
    _get_model,
    _get_principle_embeddings,
    _get_principle_anchor_embeddings,
)
from analysis.core.queries import get_all_filings
from db.models import Company, Fact
from db.session import get_session, init_db
from sentence_transformers import util

PRINCIPLE_TO_LABEL = {f"Principle{i}Member": i for i in range(1, 10)}


def main():
    init_db()
    model = _get_model()
    principle_nums, principle_embeddings = _get_principle_embeddings()
    anchor_dict = _get_principle_anchor_embeddings()

    with get_session() as session:
        for company_name in ["NIIT Learning", "Mastek", "Coal India"]:
            company = session.query(Company).filter(Company.name.ilike(f"%{company_name}%")).first()
            if company is None:
                continue
            filing = get_all_filings(session, company.id)[0]

            text_facts = (
                session.query(Fact)
                .filter(Fact.filing_id == filing.id, Fact.concept.like("%ExplanatoryTextBlock%"))
                .all()
            )

            text_to_principles: dict[str, set[int]] = {}
            for f in text_facts:
                principle_dim = f.dimensions.get("PrincipleAxis")
                text = f.value.strip()
                if principle_dim in PRINCIPLE_TO_LABEL and len(text) >= 20:
                    text_to_principles.setdefault(text, set()).add(PRINCIPLE_TO_LABEL[principle_dim])

            by_principle: dict[int, list[str]] = {}
            for text, principles in text_to_principles.items():
                if len(principles) > 1:
                    continue  # cross-principle boilerplate — excluded
                if text.strip().lower().startswith(("http://", "https://")):
                    continue
                principle_num = next(iter(principles))
                by_principle.setdefault(principle_num, []).append(text)

            correct = 0
            total = 0

            print(f"\n=== {company.name} ===")
            for true_principle, texts in sorted(by_principle.items()):
                text_embs = model.encode(texts, convert_to_tensor=True, show_progress_bar=False)
                sims_enriched = util.cos_sim(text_embs, principle_embeddings)

                for i, text in enumerate(texts):
                    p_scores = []
                    for p_idx, p in enumerate(principle_nums):
                        score_enriched = float(sims_enriched[i, p_idx])
                        anchor_sims = util.cos_sim(text_embs[i:i+1], anchor_dict[p])[0]
                        score_anchor = float(0.70 * anchor_sims.max() + 0.30 * anchor_sims.mean())
                        hybrid_score = 0.50 * score_enriched + 0.50 * score_anchor
                        p_scores.append((p, hybrid_score))

                    ranked = sorted(p_scores, key=lambda x: x[1], reverse=True)
                    predicted_principle = ranked[0][0]
                    total += 1
                    if predicted_principle == true_principle:
                        correct += 1

                # Sample print for first segment
                first_scores = []
                for p_idx, p in enumerate(principle_nums):
                    score_enriched = float(sims_enriched[0, p_idx])
                    anchor_sims = util.cos_sim(text_embs[0:1], anchor_dict[p])[0]
                    score_anchor = float(0.70 * anchor_sims.max() + 0.30 * anchor_sims.mean())
                    hybrid_score = 0.50 * score_enriched + 0.50 * score_anchor
                    first_scores.append((p, hybrid_score))
                ranked_first = sorted(first_scores, key=lambda x: x[1], reverse=True)
                match = "[PASS]" if ranked_first[0][0] == true_principle else "[FAIL]"
                print(f"  P{true_principle} ({len(texts)} segments): best-match=P{ranked_first[0][0]} "
                      f"(sim={ranked_first[0][1]:.3f}) {match}")

            if total > 0:
                print(f"  Segment-level accuracy: {correct}/{total} ({correct/total*100:.1f}%)")


if __name__ == "__main__":
    main()
