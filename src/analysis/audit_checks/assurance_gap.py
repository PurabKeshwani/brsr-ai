"""
Assurance Gap & Fact-Backing Detector (Signal 4 for Greenwashing Detection)

Cross-checks narrative disclosure claims against the company's officially-filed
numerical facts and independent third-party assurance profile.

Detects two critical disclosure gaps:
1. Fact-Backing Gap (Unsubstantiated Claim): A company makes narrative claims about
   a key metric (e.g., emissions, water, waste, energy, renewable power, CSR), but
   the corresponding structured XBRL numerical value is completely missing from
   their filed tables (Fact is NULL or absent).
2. Assurance Gap (Unverified Claim): The numerical fact exists, but carries NO
   independent external third-party assurance (or only self-certified).

This represents a major novelty for GRASP: grounding narrative rhetoric directly
in the structured regulatory fact database.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from sqlalchemy.orm import Session

from analysis.audit_checks.assurance import get_assurance_profile
from db.models import Fact, Filing

# Concepts tracked for narrative claim-to-fact grounding
TRACKED_FACT_DOMAINS: dict[str, dict] = {
    "Scope 1 Emissions": {
        "concept": "TotalScope1Emissions",
        "keywords": [r"\bscope\s*1\b", r"\bdirect\s+emissions\b"],
        "assurance_topic": "DetailsOfGreenHouseGasEmissionsAndItsIntensity",
    },
    "Scope 2 Emissions": {
        "concept": "TotalScope2Emissions",
        "keywords": [r"\bscope\s*2\b", r"\bindirect\s+emissions\b"],
        "assurance_topic": "DetailsOfGreenHouseGasEmissionsAndItsIntensity",
    },
    "Scope 3 Emissions": {
        "concept": "TotalScope3Emissions",
        "keywords": [r"\bscope\s*3\b", r"\bvalue\s+chain\s+emissions\b"],
        "assurance_topic": "DetailsOfTotalScope3EmissionsAndItsIntensity",
    },
    "Water Consumption": {
        "concept": "TotalVolumeOfWaterWithdrawal",
        "keywords": [r"\bwater\s+consumption\b", r"\bwater\s+withdrawal\b", r"\bwater\s+recycled\b"],
        "assurance_topic": "DetailsOfTheDisclosuresRelatedToWaterWithdrawal",
    },
    "Waste Management": {
        "concept": "TotalWasteGenerated",
        "keywords": [r"\bwaste\s+generated\b", r"\bhazardous\s+waste\b", r"\bwaste\s+recycled\b"],
        "assurance_topic": "DetailsRelatedToWasteManagementByTheEntity",
    },
    "Renewable Energy": {
        "concept": "TotalEnergyConsumedFromRenewableSources",
        "keywords": [r"\brenewable\s+energy\b", r"\bsolar\s+power\b", r"\bwind\s+power\b", r"\bgreen\s+energy\b"],
        "assurance_topic": "DetailsOfTotalEnergyConsumptionInJoulesOrMultiplesAndEnergyIntensity",
    },
}


class GapSeverity(Enum):
    HIGH = "high_unsubstantiated_fact_missing"
    MEDIUM = "medium_unassured_claim"
    LOW = "low_limited_assurance"
    VERIFIED = "verified_reasonable_assurance"


@dataclass
class AssuranceGapSignal:
    domain: str
    concept: str
    claim_sentence: str
    fact_found: bool
    fact_value: Optional[str]
    is_assured: bool
    assurance_level: Optional[str]
    severity: GapSeverity
    explanation: str


def check_assurance_gap(
    session: Session,
    filing_id: int,
    text: str,
) -> list[AssuranceGapSignal]:
    """Inspects a narrative text segment for specific ESG domain claims and
    verifies if the company has officially filed numerical data and third-party
    assurance for that domain in filing_id.
    """
    signals = []

    # Get assurance profile for the filing
    assurance_profile = get_assurance_profile(session, filing_id)
    assurance_by_area = {item.disclosure_area.lower(): item for item in assurance_profile.items}

    # Split text into sentences
    sentences = re.split(r"(?<=[.!?])\s+|\n+", text)

    for domain_name, config in TRACKED_FACT_DOMAINS.items():
        domain_patterns = [re.compile(kw, re.IGNORECASE) for kw in config["keywords"]]
        concept_name = config["concept"]
        assurance_topic = config["assurance_topic"].lower()

        for sent in sentences:
            if len(sent.strip()) < 15:
                continue

            # Check if sentence mentions this domain
            if any(p.search(sent) for p in domain_patterns):
                # Query database to see if numeric fact was actually filed
                fact_record = (
                    session.query(Fact)
                    .filter(Fact.filing_id == filing_id, Fact.concept.like(f"%{concept_name}%"))
                    .first()
                )

                fact_found = fact_record is not None and fact_record.value not in (None, "", "nil", "0", "NA")
                fact_value = fact_record.value if fact_found else None

                # Check assurance
                assurance_item = assurance_by_area.get(assurance_topic)
                is_assured = assurance_item.is_assured if assurance_item else False
                assurance_level = assurance_item.assurance_level if assurance_item else None

                if not fact_found:
                    sev = GapSeverity.HIGH
                    exp = f"Sentence claims narrative action on '{domain_name}', but structured XBRL numerical fact is completely missing from filing."
                elif not is_assured:
                    sev = GapSeverity.MEDIUM
                    exp = f"Fact is filed ({fact_value}), but carries no independent third-party assurance (self-reported only)."
                elif assurance_level == "Limited":
                    sev = GapSeverity.LOW
                    exp = f"Fact is filed ({fact_value}) with limited assurance."
                else:
                    sev = GapSeverity.VERIFIED
                    exp = f"Fact is filed ({fact_value}) with reasonable assurance."

                if sev in (GapSeverity.HIGH, GapSeverity.MEDIUM):
                    signals.append(
                        AssuranceGapSignal(
                            domain=domain_name,
                            concept=concept_name,
                            claim_sentence=sent.strip(),
                            fact_found=fact_found,
                            fact_value=fact_value,
                            is_assured=is_assured,
                            assurance_level=assurance_level,
                            severity=sev,
                            explanation=exp,
                        )
                    )
                break  # one signal per domain per segment

    return signals
