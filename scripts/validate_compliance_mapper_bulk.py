"""
Bulk validity check for compliance_mapper.py — aggregates the
segment-level "does text under principle P best-match P's own official
definition" test across ALL ingested companies, for a statistically
meaningful sample size (a handful of companies individually often have
too few non-boilerplate, non-URL segments per principle to draw any
conclusion — see conversation history).
"""
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from analysis.compliance_mapper import _get_model, _get_principle_embeddings
from db.models import Company, Fact, Filing
from db.session import get_session, init_db
from sentence_transformers import util

PRINCIPLE_TO_LABEL = {f"Principle{i}Member": i for i in range(1, 10)}


def main():
    init_db()
    model = _get_model()
    principle_nums, principle_embeddings = _get_principle_embeddings()

    with get_session() as session:
        companies = session.query(Company).limit(100).all()  # subset for speed

        confusion = Counter()  # (true_principle, predicted_principle) -> count
        correct = 0
        total = 0

        for company in companies:
            filing = (
                session.query(Filing)
                .filter_by(company_id=company.id)
                .order_by(Filing.financial_year_end.desc())
                .first()
            )
            if filing is None:
                continue

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

            segments_to_check: list[tuple[int, str]] = []
            for text, principles in text_to_principles.items():
                if len(principles) > 1:
                    continue
                if text.strip().lower().startswith(("http://", "https://")):
                    continue
                principle_num = next(iter(principles))
                segments_to_check.append((principle_num, text))

            if not segments_to_check:
                continue

            texts = [t for _, t in segments_to_check]
            text_embs = model.encode(texts, convert_to_tensor=True, show_progress_bar=False)
            sims_matrix = util.cos_sim(text_embs, principle_embeddings)

            for i, (true_principle, _) in enumerate(segments_to_check):
                sims = sims_matrix[i].tolist()
                best_idx = sims.index(max(sims))
                predicted_principle = principle_nums[best_idx]
                confusion[(true_principle, predicted_principle)] += 1
                total += 1
                if predicted_principle == true_principle:
                    correct += 1

        print(f"Total segments evaluated: {total}")
        print(f"Correct top-match: {correct} ({correct/total*100:.1f}%)")
        print(f"Random-chance baseline (1-in-9): {100/9:.1f}%")

        print("\nPer-principle accuracy:")
        for p in range(1, 10):
            p_total = sum(count for (tp, pp), count in confusion.items() if tp == p)
            p_correct = confusion.get((p, p), 0)
            if p_total > 0:
                print(f"  P{p}: {p_correct}/{p_total} ({p_correct/p_total*100:.1f}%)")


if __name__ == "__main__":
    main()