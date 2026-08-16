"""
Verification script — tests the semantic vagueness layer against a small
set of hand-picked real and synthetic sentences to sanity-check the
reference pools before running it across the full dataset.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from analysis.vagueness_semantic import analyze_semantic_vagueness

TEST_SENTENCES = [
    # Paraphrased vague claims (NOT using exact lexicon phrases) — the gap
    # this layer is meant to fill:
    "Our organisation continues its journey towards a better tomorrow for all stakeholders.",
    "The team remains focused on delivering value through sustained dedication to our principles.",
    # Genuinely quantified claims:
    "Carbon emissions fell by 12% year-on-year, from 500 tCO2e to 440 tCO2e.",
    "The company employed 3,204 people as of March 2026, of whom 41% were women.",
    # Neutral/unrelated text (should not be strongly flagged either way):
    "The registered office of the company is located in Mumbai, Maharashtra.",
]

for sentence in TEST_SENTENCES:
    result = analyze_semantic_vagueness(sentence)
    print(f"\nText: {sentence}")
    print(f"  sim_to_vague={result.max_similarity_to_vague}  sim_to_quantified={result.max_similarity_to_quantified}")
    print(f"  Flagged vague: {result.is_flagged_vague}")