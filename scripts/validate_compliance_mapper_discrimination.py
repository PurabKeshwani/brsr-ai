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

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from analysis.compliance_mapper import _get_model, _get_principle_embeddings
from analysis.queries import get_all_filings
from db.models import Company, Fact
from db.session import get_session, init_db
from sentence_transformers import util

PRINCIPLE_TO_LABEL = {f"Principle{i}Member": i for i in range(1, 10)}


def main():
    init_db()
    model = _get_model()
    principle_nums, principle_embeddings = _get_principle_embeddings()

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
                # Also exclude bare weblink/URL text — not meaningful for
                # semantic alignment against an abstract principle statement.
                if text.strip().lower().startswith(("http://", "https://")):
                    continue
                principle_num = next(iter(principles))
                by_principle.setdefault(principle_num, []).append(text)

            correct = 0
            total = 0

            print(f"\n=== {company.name} ===")
            for true_principle, texts in sorted(by_principle.items()):
                text_embs = model.encode(texts, convert_to_tensor=True)
                sims_matrix = util.cos_sim(text_embs, principle_embeddings)  # [n_texts, 9]

                for i, text in enumerate(texts):
                    sims = sims_matrix[i].tolist()
                    best_idx = sims.index(max(sims))
                    predicted_principle = principle_nums[best_idx]
                    total += 1
                    if predicted_principle == true_principle:
                        correct += 1

                # Print one representative line per principle for eyeballing
                sims_first = sims_matrix[0].tolist()
                best_idx_first = sims_first.index(max(sims_first))
                match = "✓" if principle_nums[best_idx_first] == true_principle else "✗"
                print(f"  P{true_principle} ({len(texts)} segments): sample best-match=P{principle_nums[best_idx_first]} "
                      f"(sim={max(sims_first):.3f}) {match}")

            if total > 0:
                print(f"  Segment-level accuracy: {correct}/{total} ({correct/total*100:.1f}%)")


if __name__ == "__main__":
    main()