"""
XGBoost Meta-Classifier — Feature Extraction (Phase 3)

Combines both human-labeled validation batches (30 + 50 = 80 samples) and
extracts a small, interpretable feature set from each text segment, using
the already-validated lexicon and semantic layers from Phase D — rather
than feeding raw text to XGBoost (which would need far more than 80
samples to learn anything from token-level features).

Features (5 total, deliberately kept small given n=80):
  - hedging_density: lexicon hedging-term count / word count
  - has_kpi: binary, whether any KPI/numeric-entity pattern matched
  - hedging_term_count: raw count (in addition to density, since very
    short segments can have high density from a single term)
  - semantic_sim_to_vague: best sentence-level cosine similarity to the
    vague reference pool
  - semantic_sim_to_quantified: best sentence-level cosine similarity to
    the quantified reference pool

This lets XGBoost learn a DATA-DRIVEN decision boundary over these
features, as an explicit comparison against Phase D's HAND-TUNED
threshold rules (is_flagged_vague logic) — the ablation this project's
paper discusses (see conversation history).
"""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from analysis.vagueness_lexicon import analyze_vagueness
from analysis.vagueness_semantic import analyze_semantic_vagueness

BATCH1_PATH = Path("data/validation/vagueness_validation_sample.csv")
BATCH2_PATH = Path("data/validation/vagueness_validation_sample_batch2.csv")
OUTPUT_PATH = Path("data/validation/xgboost_features.csv")


def load_labeled_rows(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    labeled = [r for r in rows if r["human_label"].strip() != ""]
    print(f"{path.name}: {len(labeled)} / {len(rows)} rows labeled")
    return labeled


def main():
    all_rows = load_labeled_rows(BATCH1_PATH) + load_labeled_rows(BATCH2_PATH)
    print(f"Total labeled samples: {len(all_rows)}")

    output_rows = []
    for row in all_rows:
        text = row["text"]
        human_label = int(row["human_label"])

        lexicon_result = analyze_vagueness(text)
        semantic_result = analyze_semantic_vagueness(text)

        word_count = max(len(text.split()), 1)

        output_rows.append({
            "text": text,
            "hedging_density": lexicon_result.hedging_density,
            "hedging_term_count": len(lexicon_result.hedging_terms_found),
            "has_kpi": int(lexicon_result.has_kpi),
            "semantic_sim_to_vague": semantic_result.max_similarity_to_vague,
            "semantic_sim_to_quantified": semantic_result.max_similarity_to_quantified,
            "word_count": word_count,
            "human_label": human_label,
        })

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(output_rows[0].keys()))
        writer.writeheader()
        writer.writerows(output_rows)

    print(f"\nFeatures written to {OUTPUT_PATH}")
    positive = sum(r["human_label"] for r in output_rows)
    print(f"Class balance: {positive} vague / {len(output_rows) - positive} not-vague")


if __name__ == "__main__":
    main()