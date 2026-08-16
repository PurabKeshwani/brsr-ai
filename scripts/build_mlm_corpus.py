"""
Domain-Adaptive Pretraining — Corpus Builder (Phase: Domain Pretraining, Step 1)

Extracts every unique, non-trivial narrative text segment across ALL
ingested companies (regardless of PrincipleAxis label — unlike
build_training_dataset.py, this corpus is for UNSUPERVISED masked
language modeling, so no label is needed) and writes it as a plain-text
corpus, one segment per line, for use with HuggingFace's MLM training
pipeline.

Deduplicated at the GLOBAL level (across all companies), not per-company
as in build_training_dataset.py — for MLM pretraining, seeing the same
boilerplate sentence from many companies repeatedly is actually fine (it
reinforces common domain phrasing), so this dedup is only to avoid
wasting compute on byte-identical duplicate lines, not a correctness
requirement like the labeled dataset had.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from db.models import Fact
from db.session import get_session, init_db

OUTPUT_PATH = Path("data/training/mlm_corpus.txt")
MIN_TEXT_LENGTH = 20


def main():
    init_db()
    with get_session() as session:
        facts = session.query(Fact).filter(Fact.concept.like("%ExplanatoryTextBlock%")).all()

        unique_texts = set()
        for f in facts:
            text = f.value.strip().replace("\n", " ").replace("\r", " ")
            text = " ".join(text.split())  # collapse repeated whitespace
            if len(text) >= MIN_TEXT_LENGTH:
                unique_texts.add(text)

        print(f"Total unique non-trivial texts: {len(unique_texts)}")

        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(OUTPUT_PATH, "w", encoding="utf-8") as out:
            for text in sorted(unique_texts):  # sorted for reproducibility, not semantically meaningful
                out.write(text + "\n")

        print(f"Written to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()