"""
Phase B — Dataset Builder (v2: Clean + Enriched)

WHAT CHANGED FROM v1 (and why):
─────────────────────────────────────────────────────────────────────────
1. NOISE FILTERING: v1 used MIN_TEXT_LENGTH = 20 *characters* — so bare
   URLs like "https://company.com/csr-policy.pdf" (40+ chars) or ISO
   cert strings like "ISO 9001:2015, ISO 14001:2015" passed through.
   An audit showed that 46.5% of training samples (1,579 of 3,393) had
   fewer than 15 *words*, most being bare links or cert lists that
   contain zero principle-specific semantics. v2 strips URLs, filters on
   word count (MIN_WORD_COUNT = 15), and drops boilerplate phrases like
   "Not Applicable" or "Nil".

2. SECTION C CONCEPT MAPPING: v1 only collected facts that had an
   explicit PrincipleAxis dimension — these come from Section B's
   summary tables (policy weblinks, cert names, commitment text). But
   the BRSR taxonomy's Section C contains 40+ principle-specific
   question-answer concepts (e.g. "AntiCorruptionOrAntiBriberyPolicy…"
   is always P1, "DetailsOfWasteManagementPractices…" is always P6)
   that have NO PrincipleAxis dimension because their principle is
   implicit in the concept name. These are the *real* narratives: 800-
   2600 chars of descriptive, domain-rich text — exactly what a
   classifier needs. An audit found 42,022 such facts with >100 chars.
   v2 maps these concepts to their principle using a curated dictionary
   (SECTION_C_CONCEPT_TO_LABEL).

3. NotesPrincipleX CONCEPTS: The XBRL taxonomy has 9 "catch-all" notes
   fields — NotesPrinciple1ExplanatoryTextBlock through …9 — where
   companies dump free-form narrative under each principle. These have
   NO PrincipleAxis dimension, but the principle is baked into the
   concept name. An audit found 3,386 such facts with >100 chars, avg
   500-2600 chars each. v2 maps these automatically.

4. ALL FILINGS, NOT JUST LATEST: v1 used .first() to pick only the
   latest filing per company (1 of potentially 2). The DB has 1,172
   filings across 1,164 companies (some have FY25 AND FY26). v2 uses
   all filings, increasing data volume and providing year-over-year
   variation in corporate language.

5. DEDUPLICATION: same (company, concept, text) methodology as v1, but
   extended to also deduplicate across the Section C source (which
   doesn't have a PrincipleAxis dimension but gets a label from the
   concept name). Cross-source dedup ensures a text that appears in
   both Section B and Section C under the same principle is counted
   only once, and contradictory labels across sources are discarded.

Output: three CSV files (train/val/test) with columns [text, label,
principle_id, company_name, cin, source] — label is 0-8, source is
"section_b", "section_c", or "notes_principle".
"""
from __future__ import annotations

import csv
import random
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from db.models import Company, Fact, Filing
from db.session import get_session, init_db

OUTPUT_DIR = Path("data/training")
TRAIN_RATIO, VAL_RATIO, TEST_RATIO = 0.70, 0.15, 0.15
RANDOM_SEED = 42

PRINCIPLE_TO_LABEL = {f"Principle{i}Member": i - 1 for i in range(1, 10)}

# ── Noise filtering ──────────────────────────────────────────────────────
MIN_WORD_COUNT = 15  # minimum *words* of real content after stripping URLs
URL_PATTERN = re.compile(r'https?://\S+|www\.\S+', re.IGNORECASE)

# Boilerplate phrases that carry zero principle-specific information
BOILERPLATE_PHRASES = {
    "not applicable", "nil", "none", "na", "n/a", "n.a.",
    "refer to website", "refer website", "please refer to the website",
    "refer annual report", "refer to annual report",
    "not applicable for the current financial year",
}


def is_clean_narrative(text: str) -> bool:
    """Returns True if the text is a genuine narrative worth training on.
    Strips URLs, checks word count, and filters boilerplate."""
    # Strip all URLs first
    cleaned = URL_PATTERN.sub('', text).strip()
    # Collapse whitespace
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    # Check against boilerplate
    if cleaned.lower() in BOILERPLATE_PHRASES:
        return False
    # Word count on the cleaned (URL-free) text
    words = cleaned.split()
    if len(words) < MIN_WORD_COUNT:
        return False
    return True


# ── Section C: concept → principle label mapping ─────────────────────────
# These are BRSR Section C question-answer concepts whose principle is
# unambiguously determined by the concept name itself. Each concept maps
# to exactly one SEBI/NGRBC principle (0-indexed: P1=0, P2=1, …, P9=8).
#
# Mapping derived from the SEBI BRSR format (Annexure I to Circular
# SEBI/HO/CFD/CMD-2/P/CIR/2021/562), where Section C organises
# questions under numbered principles. Verified against the concept
# names' semantic content and official NGRBC principle definitions.

SECTION_C_CONCEPT_TO_LABEL: dict[str, int] = {
    # ── P1: Ethics, Transparency & Anti-Corruption ──────────────────
    "AntiCorruptionOrAntiBriberyPolicyExplanatoryTextBlock": 0,
    "DetailsOfAnyCorrectiveActionTakenOrUnderwayOnIssuesRelatedToFinesOrPenaltiesOrActionTakenByRegulatorsOrLawEnforcementAgenciesOrJudicialInstitutionsOnCasesOfCorruptionAndConflictsOfInterestExplanatoryTextBlock": 0,
    "DetailsOfTheEntityHaveProcessesInPlaceToAvoidOrManageConflictOfInterestsInvolvingMembersOfTheBoardExplanatoryTextBlock": 0,
    "DetailsOfTheHighestAuthorityResponsibleForImplementationAndOversightOfTheBusinessResponsibilityPolicyExplanatoryTextBlock": 0,
    "DetailsOfSpecifiedCommitteeOfTheBoardOrDirectorResponsibleForDecisionMakingOnSustainabilityRelatedIssuesExplanatoryTextBlock": 0,
    "BriefOfTheMonetaryCaseForPenaltyOrFineExplanatoryTextBlock": 0,

    # ── P2: Sustainable Products & Services ─────────────────────────
    "DescribeTheProcessesInPlaceToSafelyReclaimYourProductsForReusingRecyclingAndDisposingAtTheEndOfLifeForEWasteExplanatoryTextBlock": 1,
    "DescribeTheProcessesInPlaceToSafelyReclaimYourProductsForReusingRecyclingAndDisposingAtTheEndOfLifeForHazardousWasteExplanatoryTextBlock": 1,
    "DescribeTheProcessesInPlaceToSafelyReclaimYourProductsForReusingRecyclingAndDisposingAtTheEndOfLifeForOtherWasteExplanatoryTextBlock": 1,
    "DetailsOfProductInformationOnTheProductOverAndAboveWhatIsMandatedAsPerLocalLawsExplanatoryTextBlock": 1,
    "WeblinkWhereInformationOnProductsAndServicesOfTheEntityCanBeAccessedExplanatoryTextBlock": 1,
    "StepsTakenToAddressTheWasteCollectionPlanExplanatoryTextBlock": 1,

    # ── P3: Employee Wellbeing & Safety ─────────────────────────────
    "DescribeTheMeasuresTakenByTheEntityToEnsureASafeAndHealthyWorkPlaceExplanatoryTextBlock": 2,
    "DesclosureOfTheProcessesUsedToIdentifyWorkRelatedHazardsAndAssessRisksOnARoutineAndNonRoutineBasisByTheEntityExplanatoryTextBlock": 2,
    "DetailsOfOccupationalHealthAndSafetyManagementSystemExplanatoryTextBlock": 2,
    "DetailsOfMechanismAvailableToReceiveAndRedressGrievancesForPermanentEmployeesExplanatoryTextBlock": 2,
    "DetailsOfMechanismAvailableToReceiveAndRedressGrievancesForOtherThanPermanentEmployeesExplanatoryTextBlock": 2,
    "DetailsOfMechanismAvailableToReceiveAndRedressGrievancesForPermanentWorkersExplanatoryTextBlock": 2,
    "DetailsOfMechanismAvailableToReceiveAndRedressGrievancesForOtherThanPermanentWorkersExplanatoryTextBlock": 2,
    "DetailsOfAnyCorrectiveActionTakenOrUnderwayToAddressSafetyRelatedIncidentsOfYourPlantsAndOfficesThatWereAssessedExplanatoryTextBlock": 2,
    "DetailsOfAnyCorrectiveActionsTakenOrUnderwayToAddressSignificantRisksOrConcernsArisingFromTheAssessmentsOfPlantAndOfficeExplanatoryTextBlock": 2,
    "MechanismsToPreventAdverseConsequencesToTheComplainantInDiscriminationAndHarassmentCasesExplanatoryTextBlock": 2,

    # ── P4: Stakeholder Engagement ──────────────────────────────────
    "DescribeTheProcessesForIdentifyingKeyStakeholderGroupsOfTheEntityExplanatoryTextBlock": 3,
    "ProvideTheProcessesForConsultationBetweenStakeholdersAndTheBoardOnEconomicEnvironmentalAndSocialTopicsOrIfConsultationIsDelegatedHowIsFeedbackFromSuchConsultationsProvidedToTheBoardExplanatoryTextBlock": 3,
    "DetailsOfInstancesAsToHowTheInputsReceivedFromStakeholdersOnTheseTopicsWereIncorporatedIntoPoliciesAndActivitiesOfTheEntityExplanatoryTextBlock": 3,

    # ── P5: Human Rights ────────────────────────────────────────────
    "DescribeTheInternalMechanismsInPlaceToRedressGrievancesRelatedToHumanRightsIssuesExplanatoryTextBlock": 4,
    "DetailsOfTheScopeAndCoverageOfAnyHumanRightsDueDiligenceConductedExplanatoryTextBlock": 4,
    "DetailsOfABusinessProcessBeingModifiedOrIntroducedAsAResultOfAddressingHumanRightsGrievancesOrComplaintsExplanatoryTextBlock": 4,

    # ── P6: Environment ─────────────────────────────────────────────
    "DetailsOfWasteManagementPracticesAdoptedInYourEstablishmentsAndTheStrategyAdoptedByCompanyToReduceUsageOfHazardousAndToxicChemicalsExplanatoryTextBlock": 5,
    "DetailsOfProjectRelatedToReducingGreenHouseGasEmissionExplanatoryTextBlock": 5,
    "DetailsOfCoverageAndImplementationIfForZeroLiquidDischargeExplanatoryTextBlock": 5,
    "DetailsOfSignificantDirectAndIndirectImpactOfTheEntityOnBiodiversityInSuchAreasAlongWithPreventionAndRemediationActivitiesExplanatoryTextBlock": 5,
    "DiscloseAnySignificantAdverseImpactToTheEnvironmentArisingFromTheValueChainOfTheEntityWhatMitigationOrAdaptationMeasuresHaveBeenTakenByTheEntityInThisRegardExplanatoryTextBlock": 5,
    "DiscloseWhetherTargetsSetUnderThePatSchemeHaveBeenAchievedInCaseTargetsHaveNotBeenAchievedThenProvideTheRemedialActionTakenExplanatoryTextBlock": 5,

    # ── P7: Public Policy ───────────────────────────────────────────
    "DetailsOfMeasuresUndertakenByTheEntityToEnsureThatStatutoryDuesHaveBeenDeductedAndDepositedByTheValueChainPartnersExplanatoryTextBlock": 6,

    # ── P8: Inclusive Growth & Community ─────────────────────────────
    "DescribeTheMechanismsToReceiveAndRedressGrievancesOfTheCommunityExplanatoryTextBlock": 7,
    "DetailsOfInstancesOfEngagementWithAndActionsTakenToAddressTheConcernsOfVulnerableMarginalizedStakeholderGroupsExplanatoryTextBlock": 7,

    # ── P9: Consumer Responsibility ─────────────────────────────────
    "DescribeTheMechanismsInPlaceToReceiveAndRespondToConsumerComplaintsAndFeedbackExplanatoryTextBlock": 8,
    "ABriefOnTypesOfCustomersExplanatoryTextBlock": 8,
    "DetailsOfAnyCorrectiveActionsTakenOrUnderwayOnIssuesRelatingToAdvertisingAndDeliveryOfEssentialServicesOrCyberSecurityAndDataPrivacyOrRecallsOrPenaltyOrActionTakenByRegulatoryAuthoritiesOnSafetyOfProductsOrServicesExplanatoryTextBlock": 8,
    "DetailsOfImpactOfDataBreachesExplanatoryTextBlock": 8,
    "StepsTakenToInformAndEducateConsumersAboutSafeAndResponsibleUsageOfProductsAndOrServicesExplanatoryTextBlock": 8,
    "MechanismsInPlaceToInformConsumersOfAnyRiskOfDisruptionOrDiscontinuationOfEssentialServicesExplanatoryTextBlock": 8,
}


# NotesPrincipleX — catch-all notes fields whose principle is in the name
NOTES_PRINCIPLE_CONCEPTS = {
    f"NotesPrinciple{i}ExplanatoryTextBlock": i - 1 for i in range(1, 10)
}


# ── Collection ────────────────────────────────────────────────────────────

def collect_labeled_samples(session) -> list[dict]:
    """Collects labeled text from THREE sources:
    1. Section B: PrincipleAxis-dimensioned ExplanatoryTextBlock facts
    2. Section C: concept-name-mapped narrative questions
    3. NotesPrincipleX: free-form notes per principle

    Uses ALL filings per company (not just latest). Deduplicates across
    all sources using (company_id, concept, text) -> set of labels,
    discarding contradictory-label entries.
    """
    companies = session.query(Company).all()
    stats = {"section_b": 0, "section_c": 0, "notes_principle": 0,
             "noise_filtered": 0, "contradictory": 0}

    # Dedup: (company_id, concept, text) -> {label: source}
    all_labeled: dict[tuple[int, str, str], dict[int, str]] = defaultdict(dict)

    for company in companies:
        filings = session.query(Filing).filter_by(company_id=company.id).all()

        for filing in filings:
            text_facts = (
                session.query(Fact)
                .filter(Fact.filing_id == filing.id,
                        Fact.concept.like("%ExplanatoryTextBlock%"))
                .all()
            )

            for f in text_facts:
                if not f.value:
                    continue
                raw_text = f.value.strip()
                if not is_clean_narrative(raw_text):
                    stats["noise_filtered"] += 1
                    continue

                # Clean URLs and collapse whitespace for consistent training text
                clean_text = URL_PATTERN.sub('', raw_text).strip()
                clean_text = re.sub(r'\s+', ' ', clean_text).strip()

                label = None
                source = None

                # Source 1: Section B — PrincipleAxis dimension
                principle_dim = (f.dimensions or {}).get("PrincipleAxis")
                if principle_dim in PRINCIPLE_TO_LABEL:
                    label = PRINCIPLE_TO_LABEL[principle_dim]
                    source = "section_b"

                # Source 2: Section C — concept name mapping
                elif f.concept in SECTION_C_CONCEPT_TO_LABEL:
                    label = SECTION_C_CONCEPT_TO_LABEL[f.concept]
                    source = "section_c"

                # Source 3: NotesPrincipleX
                elif f.concept in NOTES_PRINCIPLE_CONCEPTS:
                    label = NOTES_PRINCIPLE_CONCEPTS[f.concept]
                    source = "notes_principle"

                if label is None:
                    continue

                # Dedup key: (company_id, concept, cleaned text)
                dedup_key = (company.id, f.concept, clean_text)
                existing = all_labeled[dedup_key]

                if label in existing:
                    continue  # same label already recorded — skip duplicate
                existing[label] = source

    # Build final sample list, discarding contradictory labels
    samples = []
    companies_by_id = {c.id: c for c in companies}

    for (company_id, concept, text), labels_dict in all_labeled.items():
        if len(labels_dict) > 1:
            stats["contradictory"] += 1
            continue
        label, source = next(iter(labels_dict.items()))
        company = companies_by_id[company_id]
        stats[source] += 1
        samples.append({
            "text": text,
            "label": label,
            "principle_id": f"Principle{label + 1}Member",
            "company_name": company.name,
            "cin": company.cin,
            "source": source,
        })

    print(f"\n  Collection statistics:")
    print(f"    Section B (PrincipleAxis):  {stats['section_b']:,}")
    print(f"    Section C (concept map):    {stats['section_c']:,}")
    print(f"    NotesPrincipleX:            {stats['notes_principle']:,}")
    print(f"    Noise-filtered (URLs/short):{stats['noise_filtered']:,}")
    print(f"    Contradictory-label dropped:{stats['contradictory']:,}")

    return samples


def stratified_split(samples: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    """Splits samples into train/val/test, preserving each class's
    proportion in every split (stratified sampling) — matches the
    approach described for the original 12,340-segment dataset, applied
    here to our weakly-supervised set instead."""
    by_label = defaultdict(list)
    for s in samples:
        by_label[s["label"]].append(s)

    rng = random.Random(RANDOM_SEED)
    train, val, test = [], [], []

    for label, group in by_label.items():
        rng.shuffle(group)
        n = len(group)
        n_train = int(n * TRAIN_RATIO)
        n_val = int(n * VAL_RATIO)

        train.extend(group[:n_train])
        val.extend(group[n_train : n_train + n_val])
        test.extend(group[n_train + n_val :])

    rng.shuffle(train)
    rng.shuffle(val)
    rng.shuffle(test)
    return train, val, test


def write_csv(path: Path, samples: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["text", "label", "principle_id", "company_name", "cin", "source"]
        )
        writer.writeheader()
        writer.writerows(samples)


def main():
    init_db()
    with get_session() as session:
        samples = collect_labeled_samples(session)

    print(f"\nTotal clean labeled samples: {len(samples)}")

    label_counts = defaultdict(int)
    source_counts = defaultdict(int)
    for s in samples:
        label_counts[s["principle_id"]] += 1
        source_counts[s["source"]] += 1
    print("\nPer-principle counts:")
    for principle, count in sorted(label_counts.items()):
        print(f"  {principle}: {count}")
    print("\nPer-source counts:")
    for source, count in sorted(source_counts.items()):
        print(f"  {source}: {count}")

    train, val, test = stratified_split(samples)
    print(f"\nSplit sizes — train: {len(train)}, val: {len(val)}, test: {len(test)}")

    write_csv(OUTPUT_DIR / "train.csv", train)
    write_csv(OUTPUT_DIR / "val.csv", val)
    write_csv(OUTPUT_DIR / "test.csv", test)
    print(f"\nWritten to {OUTPUT_DIR}/train.csv, val.csv, test.csv")


if __name__ == "__main__":
    main()
