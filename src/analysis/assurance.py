"""
Assurance Coverage Analysis

BRSR XBRL filings tag each disclosure area with whether it was externally
assured, and at what level (Reasonable = higher confidence, Limited =
lower). This is a genuinely novel signal for greenwashing risk assessment:
disclosures that are self-reported with no external assurance deserve more
scrutiny than reasonably-assured ones.

REAL BUG FOUND AGAINST MASTEK DATA: SEBI's own XBRL taxonomy is NOT
consistent in how it names the "AssuranceSubTypeFor..." tag relative to
its paired "Whether...IsAssuredByAssurer" tag. Verified real examples:
  - "WhetherCSRIsApplicableAsPerSection135..." pairs with
    "AssuranceSubTypeForWhetherCSRIsApplicableAsPerSection135..."
    (keeps the "Whether" prefix)
  - "WhetherGreenCreditsHaveBeenGenerated...IsAssuredByAssurer" pairs with
    "AssuranceSubTypeForGreenCreditsHaveBeenGenerated...IsAssuredByAssurer"
    (drops "Whether" but KEEPS "IsAssuredByAssurer")
  - Most others drop both "Whether" and "IsAssuredByAssurer" cleanly.
Fixed by trying multiple candidate topic-name variants instead of a single
exact strip, and falling back to substring matching as a last resort — a
deliberately layered approach so the common case stays a fast, exact
match and only the known-inconsistent cases pay for the fallback.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from db.models import Fact

WHETHER_PREFIX = "Whether"
WHETHER_SUFFIX = "IsAssuredByAssurer"
SUBTYPE_PREFIX = "AssuranceSubTypeFor"


@dataclass
class AssuranceItem:
    disclosure_area: str
    is_assured: bool
    assurance_level: str | None


@dataclass
class AssuranceProfile:
    items: list[AssuranceItem]

    @property
    def total_disclosure_areas(self) -> int:
        return len(self.items)

    @property
    def assured_count(self) -> int:
        return sum(1 for i in self.items if i.is_assured)

    @property
    def reasonable_count(self) -> int:
        return sum(1 for i in self.items if i.assurance_level == "Reasonable")

    @property
    def limited_count(self) -> int:
        return sum(1 for i in self.items if i.assurance_level == "Limited")

    @property
    def unassured_count(self) -> int:
        return self.total_disclosure_areas - self.assured_count

    @property
    def assured_but_level_unresolved_count(self) -> int:
        """Assured=true but we couldn't determine a level — should be 0
        after the topic-name fallback fix; kept visible (not silently
        folded into unassured_count) so a regression is immediately
        obvious rather than quietly miscounted as 'unassured'."""
        return sum(1 for i in self.items if i.is_assured and i.assurance_level is None)

    @property
    def reasonable_assurance_pct(self) -> float:
        if self.total_disclosure_areas == 0:
            return 0.0
        return round(self.reasonable_count / self.total_disclosure_areas * 100, 1)

    def low_assurance_areas(self) -> list[str]:
        return [i.disclosure_area for i in self.items if i.assurance_level != "Reasonable"]


def _extract_topic(whether_concept: str) -> str:
    topic = whether_concept
    if topic.startswith(WHETHER_PREFIX):
        topic = topic[len(WHETHER_PREFIX):]
    if topic.endswith(WHETHER_SUFFIX):
        topic = topic[: -len(WHETHER_SUFFIX)]
    return topic


def _candidate_subtype_concepts(whether_concept: str, topic: str) -> list[str]:
    """Returns every subtype-tag name variant worth trying, in order of
    how common each pattern is (most-stripped first, since that's the
    common case) — see module docstring for the three real naming
    patterns this was built from."""
    return [
        f"{SUBTYPE_PREFIX}{topic}",                                    # common case: both stripped
        f"{SUBTYPE_PREFIX}{WHETHER_PREFIX}{topic}",                     # "Whether" kept
        f"{SUBTYPE_PREFIX}{topic}{WHETHER_SUFFIX}",                     # "IsAssuredByAssurer" kept
        f"{SUBTYPE_PREFIX}{whether_concept}",                           # nothing stripped at all
    ]


def get_assurance_profile(session: Session, filing_id: int) -> AssuranceProfile:
    facts = session.query(Fact).filter_by(filing_id=filing_id).all()

    whether_facts = {
        f.concept: f.value for f in facts
        if f.concept.startswith(WHETHER_PREFIX) and f.concept.endswith(WHETHER_SUFFIX)
    }
    subtype_facts = {f.concept: f.value for f in facts if f.concept.startswith(SUBTYPE_PREFIX)}

    items = []
    for whether_concept, value in whether_facts.items():
        topic = _extract_topic(whether_concept)
        is_assured = value.strip().lower() == "true"

        assurance_level = None
        if is_assured:
            for candidate in _candidate_subtype_concepts(whether_concept, topic):
                if candidate in subtype_facts:
                    assurance_level = subtype_facts[candidate]
                    break

        items.append(AssuranceItem(disclosure_area=topic, is_assured=is_assured, assurance_level=assurance_level))

    return AssuranceProfile(items=items)