"""
Greenwashing Vagueness Detection — Lexicon + KPI Entity Layer (Phase D1)

This is DISTINCT from analysis/greenwashing.py (which detects a specific
contradiction: a narrative claim of improvement vs. an XBRL-filed numeric
trend moving the opposite way). This module instead flags GENERAL
vagueness — hedging/aspirational language unsupported by any quantified
KPI — regardless of whether a matching numeric XBRL concept exists to
contradict it. Both signals are meant to be surfaced together in the
final system, not merged into one.

Lexicon categories and hedging-density/KPI-detection methodology follow
the structure described in the project report (150+ term dictionary
across 4 semantic categories; a segment is flagged as vague if it has
high hedging-term density AND no detected numerical KPI). The lexicon
below is a starting set assembled from the report's own sample terms plus
common ESG-reporting hedging phrases; it is expected to be refined once
tested against real filing text (see verification step after this file).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# Organized into the four categories described in the report. Each entry
# is matched case-insensitively as a whole-phrase substring with word
# boundaries, to avoid partial-word false positives (e.g. matching "aim"
# inside "claimed").
HEDGING_LEXICON: dict[str, list[str]] = {
    "aspirational_intent": [
        "aim to", "aims to", "aspire to", "aspires to", "strive to", "strives to",
        "committed to achieving", "working towards", "working toward",
        "endeavour to", "endeavor to", "hope to", "plan to", "intend to",
        "intends to", "ambition to", "seek to", "seeks to", "committed to ensuring",
        "committed to building", "committed to fostering", "committed to promoting",
    ],
    "conditional_qualifiers": [
        "subject to", "where feasible", "as far as practicable", "as far as possible",
        "to the extent possible", "to the extent feasible", "where applicable",
        "conditions permitting", "contingent upon", "if circumstances allow",
        "wherever possible", "as and when required", "as may be required",
    ],
    "vague_temporal_references": [
        "in due course", "over time", "in the near future", "progressively",
        "in the coming years", "eventually", "going forward", "in subsequent periods",
        "at the earliest opportunity", "in the foreseeable future", "shortly",
        "in the long run", "in the long term",
    ],
    "unverifiable_quantifiers": [
        "significant progress", "substantial improvement", "considerable efforts",
        "meaningful contribution", "major steps", "notable achievements",
        "extensive measures", "comprehensive approach", "robust framework",
        "significant strides", "considerable progress", "marked improvement",
        "sizeable investment", "wide-ranging initiatives", "holistic approach",
    ],
}

ALL_HEDGING_TERMS: list[str] = [term for terms in HEDGING_LEXICON.values() for term in terms]

_HEDGING_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(term) for term in ALL_HEDGING_TERMS) + r")\b",
    re.IGNORECASE,
)

# KPI / numeric-entity detection — deliberately regex-based rather than a
# full NER model for this first version (fast, deterministic, and BRSR
# narrative text follows fairly consistent numeric-mention patterns:
# percentages, currency amounts, physical quantities with units, and
# explicit counts). Flags a segment as having AT LEAST ONE quantified
# reference if any pattern matches.
# KPI / numeric-entity detection — deliberately regex-based rather than a
# full NER model for this first version (fast, deterministic, and BRSR
# narrative text follows fairly consistent numeric-mention patterns:
# percentages, currency amounts, physical quantities with units, and
# explicit counts). Flags a segment as having AT LEAST ONE quantified
# reference if any pattern matches.
_KPI_PATTERNS = [
    re.compile(r"\d+(\.\d+)?\s*%"),                                    # percentages: "45%", "12.5 %"
    re.compile(r"\b(?:rs\.?|inr|₹)\s*\d+[\d,]*(?:\.\d+)?\s*(?:crore|lakh|cr|mn|bn)?\b", re.IGNORECASE),  # currency with mandatory digits and word boundary
    re.compile(r"\b\d{1,3}(,\d{2,3})+(\.\d+)?\b"),                      # large formatted numbers: "1,23,456"
    re.compile(r"\b\d+(\.\d+)?\s*(?:tonnes?|kg|mt|gj|[kmgt]?w|[kmgt]?wh|kl|liters?|litres?)\b", re.IGNORECASE),  # units: includes MW, GW, kW, MWh, etc.
    re.compile(r"\bFY\s?\d{2,4}\b", re.IGNORECASE),                     # financial year references
    re.compile(r"\b\d+\s*(?:employees|workers|days|hours|incidents|complaints|units)\b", re.IGNORECASE),
    re.compile(r"\bISO\s?\d{4,5}(?::\d{4})?\b", re.IGNORECASE),           # "ISO 14001", "ISO 14001:2015"
    re.compile(r"\b(?:TSDFs?|ZLD|HIRA|HAZOP|JSA|PSSR|EHS|OHSAS|GRI|SASB|TCFD|ICC|POSH|IATF|BIS|LEED|IGBC|FSC|ETP|STP)\b", re.IGNORECASE),  # named standard systems/frameworks
    re.compile(r"\b(?:Internal Complaints Committee|Whistle\s?blower|Code of Conduct|Prevention of Sexual Harassment)\b", re.IGNORECASE),
    re.compile(r"\b[A-Z]{2,}(?:-[A-Z]{2,})+\b"),                        # named accreditation bodies as acronyms: "DNV-GL"
    re.compile(r"\bscope\s?[123]\b", re.IGNORECASE),                   # "Scope 1/2/3" emissions references
    re.compile(
        r"\bzero[\s-](?:\w+[\s-])?(?:incidents?|fatalit(?:y|ies)|injur(?:y|ies)|"
        r"waste(?:[\s-]to[\s-]landfill)?|discharge|accidents?|complaints?|defects?)\b",
        re.IGNORECASE,
    ),
]

_EVASION_PATTERN = re.compile(
    r"^(?:https?://\S+|www\.\S+|\s*refer(?: to)?\s+(?:website|portal|link)|(?:information|details)\s+(?:can be found|available)\s+on\s+website)\b",
    re.IGNORECASE,
)


@dataclass
class VaguenessAnalysis:
    text: str
    hedging_terms_found: list[str]
    hedging_density: float  # hedging term count / total word count
    has_kpi: bool
    kpi_matches: list[str]
    is_evasion: bool = False

    @property
    def is_flagged_vague(self) -> bool:
        """A segment is flagged vague if:
        1. It is a non-disclosure URL/evasion boilerplate, OR
        2. It contains hedging language AND no quantified KPI (with density >= 0.005 for long text)
        """
        if self.is_evasion:
            return True
        if len(self.hedging_terms_found) == 0:
            return False
        if self.has_kpi:
            return False
        # For substantive text (>80 words), require density >= 0.005 so a single benign phrase does not trigger
        word_count = len(self.text.split())
        if word_count > 80 and self.hedging_density < 0.005:
            return False
        return True


def analyze_vagueness(text: str) -> VaguenessAnalysis:
    cleaned = text.strip()
    is_evasion = bool(_EVASION_PATTERN.search(cleaned)) or (cleaned.startswith("http") and len(cleaned.split()) <= 5)

    hedging_matches = _HEDGING_PATTERN.findall(text)
    hedging_terms_found = [m if isinstance(m, str) else m[0] for m in hedging_matches]

    word_count = max(len(text.split()), 1)
    hedging_density = len(hedging_terms_found) / word_count

    kpi_matches = []
    for pattern in _KPI_PATTERNS:
        for match in pattern.finditer(text):
            kpi_matches.append(match.group(0))

    return VaguenessAnalysis(
        text=text,
        hedging_terms_found=hedging_terms_found,
        hedging_density=round(hedging_density, 4),
        has_kpi=len(kpi_matches) > 0,
        kpi_matches=kpi_matches,
        is_evasion=is_evasion,
    )