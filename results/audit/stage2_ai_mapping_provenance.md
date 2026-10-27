# Stage 2 — AI-Generated Concept Mapping Decisions

**Status:** AI-generated taxonomy mappings; not independently expert-validated.

These assignments extend the existing concept-to-principle map using the XBRL concept names, representative facts in the local BRSR corpus, and the matching question placement in SEBI's BRSR format. The labels are weak supervision derived from taxonomy concepts; they are not human ground truth and must not be described as expert annotations.

The code stores principle IDs as zero-based integers (`P1 = 0` through `P9 = 8`). The production dataset builder applies these assignments in `scripts/03_bert_training/build_training_dataset.py` under `AI_SECTION_C_CONCEPT_TO_LABEL`.

## AI-Assigned Concepts

| Principle | Concepts assigned by the AI mapping |
|---|---|
| P1 | `DetailsForTheEntityHaveNotApplicableAnAntiCorruptionOrAntiBriberyPolicyExplanatoryTextBlock`; `DetailsOfTheEntityHaveNotApplicableProcessesInPlaceToAvoidOrManageConflictOfInterestsInvolvingMembersOfTheBoardExplanatoryTextBlock`; `TheEntityHasNotApplicableASpecifiedCommitteeForDecisionMakingOnSustainabilityRelatedIssuesExplanatoryTextBlock` |
| P2 | `TheEntityHasNotApplicableConductedLifeCyclePerspectiveOrAssessmentsForAnyOfItsProductsOrForItsServicesExplanatoryTextBlock`; `TheEntityHasNotApplicableProductInformationOnTheProductOverAndAboveWhatIsMandatedAsPerLocalLawsExplanatoryTextBlock` |
| P3 | `AnOccupationalHealthAndSafetyManagementSystemHasBeenNotApplicableToTheEntityExplanatoryTextBlock`; `DetailsIfTheEmployeesOrWorkerOfTheEntityHaveAccessToNonOccupationalMedicalAndHealthcareServicesIsNotApplicableExplanatoryTextBlock`; `ProcessesForWorkersToReportTheWorkRelatedHazardsAndToRemoveThemselvesFromSuchRisksIsNotApplicableExplanatoryTextBlock`; `TheEntityHasNotApplicableAnEqualOpportunityPolicyAsPerTheRightsOfPersonsWithDisabilitiesAct2016ExplanatoryTextBlock`; `TheEntityHasNotApplicableTransitionAssistanceProgramsToFacilitateContinuedEmployabilityAndTheManagementOfCareerEndingsResultingFromRetirementOrTerminationOfEmploymentExplanatoryTextBlock`; `ThePremisesOrOfficesOfTheEntityAccessibleToDifferentlyAbledEmployeesAndWorkersAreNotApplicableExplanatoryTextBlock`; `WhetherAnyStepsAreBeingTakenByTheEntityIfThePremisesOrOfficesOfTheEntityNotAccessibleToDifferentlyAbledEmployeesAndWorkersExplanatoryTextBlock` |
| P5 | `HumanRightsRequirementsFormPartOfYourBusinessAgreementsAndContractsIsNotApplicableExplanatoryTextBlock` |
| P6 | `AMechanismForZeroLiquidDischargeIsNotApplicableToTheEntityExplanatoryTextBlock`; all nine `NameOfTheExternalAgency...` concepts for air emissions, water stress, energy consumption, water withdrawal, GHG emissions, Scope 3 emissions, water discharge, and waste management; `ProjectRelatedToReducingGreenHouseGasEmissionIsNotApplicableToTheEntityExplanatoryTextBlock`; `TheEntityHasNotApplicableEnvironmentalLawExplanatoryTextBlock`; `TheEntityHasNotApplicableABusinessContinuityAndDisasterManagementPlanExplanatoryTextBlock` |
| P8 | `TheEntityHasNotApplicableAPreferentialProcurementPolicyExplanatoryTextBlock` |
| P9 | `TheEntityHasNotApplicableAFrameworkOrPolicyOnCyberSecurityAndRisksRelatedToDataPrivacyExplanatoryTextBlock`; `TheEntityHasNotApplicableCarryOutAnySurveyWithRegardToConsumerSatisfactionRelatingToTheMajorProductsOrServicesExplanatoryTextBlock` |

The mapping was corrected from P7 to P3 for `DetailsOfMeasuresUndertakenByTheEntityToEnsureThatStatutoryDuesHaveBeenDeductedAndDepositedByTheValueChainPartnersExplanatoryTextBlock`. Three missed P2/P3 concepts were also added: plastics product reclamation (P2), and both value-chain health-and-safety corrective-action concepts (P3).

## Excluded Concepts

These nine concepts remain out of the single-principle training labels because the concept alone is generic, cross-cutting, or does not identify a unique principle. The monetary-action table explicitly carries an NGRBC principle per case, so its concept labels cannot safely assign a fixed class.

- `BriefOfTheMonetaryCaseForCompoundingFeeExplanatoryTextBlock`
- `BriefOfTheMonetaryCaseForImprisonmentExplanatoryTextBlock`
- `BriefOfTheMonetaryCaseForPunishmentExplanatoryTextBlock`
- `BriefOfTheMonetaryCaseForSettlementExplanatoryTextBlock`
- `DetailsForGrievanceRedressalMechanismInPlaceIsNotApplicableExplanatoryTextBlock` — stakeholder group is not specified.
- `NotesGeneralDisclosureExplanatoryTextBlock`
- `NotesManagementAndProcessDisclosuresExplanatoryTextBlock`
- `RemarksforComplaintsExplanatoryTextBlock`
- `StatementByDirectorResponsibleForTheBusinessResponsibilityReportHighlightingESGRelatedChallengesTargetsAndAchievementsExplanatoryTextBlock`

No P7-specific narrative concept appeared in the current 103-concept clean corpus inventory. P7 still receives samples through other sources, including `PrincipleAxis` and `NotesPrinciple7`; no P7 Section C labels were fabricated.

## Taxonomy References

- [SEBI updated BRSR format, Annexure II (2023)](https://www.sebi.gov.in/sebi_data/commondocs/jul-2023/Annexure_II-Updated-BRSR_p.PDF) — principle-wise question placement, including P2, P3, P6, P8, and P9.
- [SEBI BRSR Master Circular (2023)](https://www.sebi.gov.in/sebi_data/attachdocs/jul-2023/1689087475880.pdf) — principle-wise requirements and generic monetary enforcement table.

## Reporting Rule

Report these labels as **AI-generated concept mapping / weak supervision**. Do not claim expert verification, human annotation, or use them as ground truth for label-quality claims. Any dataset rebuild changes training inputs; all model metrics based on the earlier dataset must be treated as belonging to the earlier version until retraining and evaluation are completed.

## Rebuilt Dataset Snapshot

The user rebuilt the dataset after applying the AI mappings. Builder output on 2026-10-17:

| Source / split | Rows |
|---|---:|
| Section B (`PrincipleAxis`) | 2,479 |
| Section C (concept map, including AI weak labels) | 36,513 |
| NotesPrincipleX | 3,417 |
| **Total** | **42,409** |
| Train | 29,683 |
| Validation | 6,358 |
| Test | 6,368 |

All source counts and split counts sum to 42,409. The builder also reports 36,491 noise-filtered facts and 2,640 contradictory-label groups dropped. Per-principle total rows: P1 5,015; P2 5,566; P3 11,835; P4 3,128; P5 3,095; P6 5,749; P7 543; P8 2,475; P9 5,003. The previous classifier checkpoints and performance numbers were trained/evaluated on earlier data and do not describe this rebuilt dataset.
