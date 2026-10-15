"""
Greenwashing Vagueness Detection — Combined Layer (Phase D3)

Combines the lexicon-based (Phase D1) and semantic-embedding-based
(Phase D2) vagueness signals into a single score and flag, per the
report's stated methodology (5.3.3): a segment is flagged if EITHER
the hedging-density-without-KPI condition holds OR the semantic
similarity-to-vague condition holds — the two are complementary
(lexicon catches known phrases fast and cheaply; semantic catches
paraphrases the lexicon misses), not redundant.
"""
from __future__ import annotations

from dataclasses import dataclass

from analysis.vagueness.vagueness_lexicon import VaguenessAnalysis, analyze_vagueness
from analysis.vagueness.vagueness_semantic import SemanticVaguenessResult, analyze_semantic_vagueness


@dataclass
class CombinedVaguenessResult:
    text: str
    lexicon_result: VaguenessAnalysis
    semantic_result: SemanticVaguenessResult

    @property
    def is_flagged_vague(self) -> bool:
        if self.lexicon_result.is_evasion:
            return True
        if self.lexicon_result.has_kpi:
            # When verified KPI/standard evidence is present, only flag if semantic vagueness is overwhelmingly dominant
            return (
                self.semantic_result.max_similarity_to_vague >= 0.58
                and (self.semantic_result.max_similarity_to_vague - self.semantic_result.max_similarity_to_quantified) >= 0.15
            )
        return self.lexicon_result.is_flagged_vague or self.semantic_result.is_flagged_vague

    @property
    def flag_source(self) -> str:
        """Which layer(s) triggered the flag — useful for the paper's
        ablation discussion (how much does each layer contribute)."""
        if self.lexicon_result.is_evasion:
            return "evasion_url"
        lex = self.lexicon_result.is_flagged_vague
        sem = self.semantic_result.is_flagged_vague and (not self.lexicon_result.has_kpi)
        if lex and sem:
            return "both"
        if lex:
            return "lexicon_only"
        if sem:
            return "semantic_only"
        return "none"

    @property
    def clarity_score_contribution(self) -> float:
        """1.0 if NOT flagged (clear/specific), 0.0 if flagged — matches
        the report's Clarity formula direction (Section 4.9.3): Clarity
        rewards the ABSENCE of greenwashing flags."""
        return 0.0 if self.is_flagged_vague else 1.0


def analyze_combined_vagueness(text: str) -> CombinedVaguenessResult:
    return CombinedVaguenessResult(
        text=text,
        lexicon_result=analyze_vagueness(text),
        semantic_result=analyze_semantic_vagueness(text),
    )