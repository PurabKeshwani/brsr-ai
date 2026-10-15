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

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from analysis.compliance.compliance_mapper import (
    _get_model,
    _get_principle_embeddings,
    _get_principle_anchor_embeddings,
    _get_domain_adapted_model,
)
from db.models import Company, Fact, Filing
from db.session import get_session, init_db
from sentence_transformers import util

PRINCIPLE_TO_LABEL = {f"Principle{i}Member": i for i in range(1, 10)}


def main():
    init_db()
    model = _get_model()
    principle_nums, principle_embeddings = _get_principle_embeddings()
    anchor_dict = _get_principle_anchor_embeddings()

    with get_session() as session:
        companies = session.query(Company).limit(100).all()  # subset for speed

        confusion = Counter()  # (true_principle, predicted_principle) -> count
        correct_top1 = 0
        correct_top2 = 0
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
            sims_enriched = util.cos_sim(text_embs, principle_embeddings)

            for i, (true_principle, _) in enumerate(segments_to_check):
                p_scores = []
                for p_idx, p in enumerate(principle_nums):
                    score_enriched = float(sims_enriched[i, p_idx])
                    anchor_sims = util.cos_sim(text_embs[i:i+1], anchor_dict[p])[0]
                    score_anchor = float(0.70 * anchor_sims.max() + 0.30 * anchor_sims.mean())
                    hybrid_score = 0.50 * score_enriched + 0.50 * score_anchor
                    p_scores.append((p, hybrid_score))

                ranked = sorted(p_scores, key=lambda x: x[1], reverse=True)
                top1 = ranked[0][0]
                top2 = [ranked[0][0], ranked[1][0]]

                confusion[(true_principle, top1)] += 1
                total += 1
                if top1 == true_principle:
                    correct_top1 += 1
                if true_principle in top2:
                    correct_top2 += 1

        print("=================================================================")
        print("  MODE 1: ZERO-SHOT DENSE EMBEDDING ENSEMBLE (BGE + MPNet)")
        print("=================================================================")
        print(f"Total segments evaluated: {total}")
        print(f"Top-1 Accuracy: {correct_top1} ({correct_top1/total*100:.2f}%)  [Baseline was 44.27%]")
        print(f"Top-2 Accuracy: {correct_top2} ({correct_top2/total*100:.2f}%)  [Baseline was 60.05%]")
        print(f"Random-chance baseline (1-in-9): {100/9:.1f}%")

        print("\nPer-principle Top-1 accuracy (Zero-Shot):")
        for p in range(1, 10):
            p_total = sum(count for (tp, pp), count in confusion.items() if tp == p)
            p_correct = confusion.get((p, p), 0)
            if p_total > 0:
                print(f"  P{p}: {p_correct}/{p_total} ({p_correct/p_total*100:.1f}%)")

    # MODE 2: Domain-Adapted Representation Transfer
    tokenizer, sup_model = _get_domain_adapted_model()
    if sup_model is not None and tokenizer is not None:
        import torch
        import torch.nn.functional as F
        device = sup_model.device

        with get_session() as session:
            companies = session.query(Company).limit(100).all()
            confusion_sup = Counter()
            correct_sup_top1 = 0
            correct_sup_top2 = 0
            total_sup = 0

            for company in companies:
                filing = session.query(Filing).filter_by(company_id=company.id).order_by(Filing.financial_year_end.desc()).first()
                if filing is None: continue
                text_facts = session.query(Fact).filter(Fact.filing_id == filing.id, Fact.concept.like("%ExplanatoryTextBlock%")).all()
                text_to_principles = {}
                for f in text_facts:
                    principle_dim = f.dimensions.get("PrincipleAxis")
                    text = f.value.strip()
                    if principle_dim in PRINCIPLE_TO_LABEL and len(text) >= 20:
                        text_to_principles.setdefault(text, set()).add(PRINCIPLE_TO_LABEL[principle_dim])

                segments_to_check = []
                for text, principles in text_to_principles.items():
                    if len(principles) > 1 or text.strip().lower().startswith(("http://", "https://")): continue
                    principle_num = next(iter(principles))
                    segments_to_check.append((principle_num, text))

                if not segments_to_check: continue

                texts = [t for _, t in segments_to_check]
                inputs = tokenizer(texts, padding=True, truncation=True, max_length=512, return_tensors="pt").to(device)
                with torch.no_grad():
                    logits = sup_model(**inputs).logits
                    probs = F.softmax(logits, dim=1)

                for i, (true_principle, _) in enumerate(segments_to_check):
                    p_probs = probs[i].cpu().tolist()
                    ranked = sorted(range(9), key=lambda k: p_probs[k], reverse=True)
                    top1 = ranked[0] + 1
                    top2 = [ranked[0] + 1, ranked[1] + 1]

                    confusion_sup[(true_principle, top1)] += 1
                    total_sup += 1
                    if top1 == true_principle: correct_sup_top1 += 1
                    if true_principle in top2: correct_sup_top2 += 1

        print("\n=================================================================")
        print("  MODE 2: DOMAIN-ADAPTED REPRESENTATION TRANSFER (Fine-tuned BERT)")
        print("=================================================================")
        print(f"Total segments evaluated: {total_sup}")
        print(f"Top-1 Accuracy: {correct_sup_top1} ({correct_sup_top1/total_sup*100:.2f}%)  [Baseline was 44.27%]")
        print(f"Top-2 Accuracy: {correct_sup_top2} ({correct_sup_top2/total_sup*100:.2f}%)  [Baseline was 60.05%]")
        print(f"Random-chance baseline (1-in-9): {100/9:.1f}%")

        print("\nPer-principle Top-1 accuracy (Domain-Adapted Transfer):")
        for p in range(1, 10):
            p_total = sum(count for (tp, pp), count in confusion_sup.items() if tp == p)
            p_correct = confusion_sup.get((p, p), 0)
            if p_total > 0:
                print(f"  P{p}: {p_correct}/{p_total} ({p_correct/p_total*100:.1f}%)")


if __name__ == "__main__":
    main()
