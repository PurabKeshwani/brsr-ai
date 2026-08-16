"""
Truth Auditor — Unified Disclosure Verification Module

DESIGN RATIONALE (documented here because this is a deliberate departure
from a common architecture pattern, not an oversight):

A "Truth Auditor" component is often designed around MNLI (Multi-Genre
Natural Language Inference) — checking whether one text statement entails
or contradicts another text statement. That approach requires a SECOND
text source to compare against (e.g. last year's claim, a third-party
fact-check, or a reference statement), which is frequently unavailable in
the BRSR context, and even when available, text-vs-text entailment is
inherently a probabilistic guess about meaning.

This project's Truth Auditor instead performs TEXT-VS-GROUND-TRUTH
verification: every claim is checked against the SAME COMPANY'S OWN
officially-filed, audited XBRL numeric disclosure — not another piece of
prose. This is a stronger form of evidence than MNLI can offer, because
the "reference" being checked against is a regulatory fact, not another
model's or another year's text. Three real, already-validated signals are
combined here into one coherent audit report per filing:

  1. Claim-Evidence Contradiction (analysis/greenwashing.py) — narrative
     claims of improvement checked against the company's own filed
     numeric trend. Verified on real data; see that module's docstring
     for the full bug-fix history (paragraph-vs-sentence granularity,
     assurance-topic mapping, deduplication).
  2. Silent Removal (analysis/silent_removal.py) — metrics disclosed in
     a prior period that are absent from the current period, a distinct
     failure mode entailment-checking cannot catch (there's no
     "statement" to contradict when something is simply missing).
  3. Vagueness Detection (analysis/vagueness_combined.py) — hedging
     language unsupported by any KPI or specific evidence, validated at
     Precision=0.917 / Recall=0.846 / AUC-ROC=0.894 (n=30, human-labeled;
     see conversation history for the full validation and bug-fix
     methodology, including a reverted over-correction).

Each signal type answers a DIFFERENT question about disclosure
trustworthiness ("does the claim match the numbers?", "did something
disappear?", "is this claim backed by evidence at all?") — they are
deliberately not merged into a single score here, since collapsing three
distinct failure modes into one number would hide which kind of problem
was found, which matters for a human reviewer deciding what to check.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from analysis.greenwashing import GreenwashingSignal, find_claim_evidence_signals
from analysis.silent_removal import SilentRemovalFlag, find_silently_removed_metrics
from analysis.specificity_clarity_score import get_deduplicated_narrative_texts
from analysis.vagueness_combined import CombinedVaguenessResult, analyze_combined_vagueness


@dataclass
class TruthAuditorReport:
    filing_id: int
    claim_evidence_contradictions: list[GreenwashingSignal]
    silent_removals: list[SilentRemovalFlag]
    vague_segments: list[CombinedVaguenessResult]  # only the flagged ones, kept for evidence review
    total_narrative_segments_checked: int

    @property
    def total_issues_found(self) -> int:
        return (
            len(self.claim_evidence_contradictions)
            + len(self.silent_removals)
            + len(self.vague_segments)
        )

    @property
    def has_high_confidence_contradiction(self) -> bool:
        """A claim-evidence contradiction is the strongest signal this
        auditor produces — it's checked against the company's own filed
        numbers, not inferred from language alone. Any occurrence here is
        worth flagging as high-priority for human review."""
        return len(self.claim_evidence_contradictions) > 0

    def summary(self) -> str:
        lines = [
            f"Truth Auditor Report — Filing {self.filing_id}",
            f"  Narrative segments checked: {self.total_narrative_segments_checked}",
            f"  Claim-evidence contradictions (claim vs filed XBRL numbers): {len(self.claim_evidence_contradictions)}",
            f"  Silent removals (metric disclosed last period, absent now): {len(self.silent_removals)}",
            f"  Vague/unsubstantiated segments (hedging without KPI evidence): {len(self.vague_segments)}",
        ]
        return "\n".join(lines)


def run_truth_audit(session: Session, filing_id: int) -> TruthAuditorReport:
    """Runs all three verification signals against one filing and returns
    a unified report. Each sub-check reuses its own already-validated
    module rather than re-implementing logic here — see module docstring
    for why each is trusted and what it specifically catches."""
    contradictions = find_claim_evidence_signals(session, filing_id)
    removals = find_silently_removed_metrics(session, filing_id)

    texts = get_deduplicated_narrative_texts(session, filing_id)
    vague_results = []
    for text in texts:
        result = analyze_combined_vagueness(text)
        if result.is_flagged_vague:
            vague_results.append(result)

    return TruthAuditorReport(
        filing_id=filing_id,
        claim_evidence_contradictions=contradictions,
        silent_removals=removals,
        vague_segments=vague_results,
        total_narrative_segments_checked=len(texts),
    )