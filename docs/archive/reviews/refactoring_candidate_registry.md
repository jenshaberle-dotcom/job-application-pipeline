# Refactoring Candidate Registry

Purpose:

Provide a controlled inventory of naming debt, architectural debt and historical terminology before code refactoring begins.

---

## KEEP

The following concepts are considered stable and should remain primary terminology.

- Bronze Layer
- Silver Layer
- Gold Layer
- Market Evidence
- Company Vocabulary
- Candidate Intelligence
- Search-Term Value
- Capability Gap
- Ground Truth
- Source Type
- Source Role

---

## RENAME CANDIDATES

The following concepts require review before future code renaming.

### False Negative

Reason:

Current architecture focuses on market understanding rather than measurable false-negative rates.

Potential future replacements:

- Market Discovery Gap
- Coverage Gap
- Market Evidence Gap

Status:

REVIEW REQUIRED

---

### Discovery

Reason:

Discovery is currently overloaded.

Potential future specializations:

- Company Discovery
- Market Discovery
- Vocabulary Discovery

Status:

REVIEW REQUIRED

---

### Search Term

Reason:

The architecture now differentiates between:

- Search Profile Term
- Observed Vocabulary

Status:

REVIEW REQUIRED

---

### Source Purpose

Reason:

Replaced conceptually by Source Role.

Status:

RENAME CANDIDATE

---

## HISTORICAL ARTIFACTS

Review for preservation rather than removal.

Potential examples:

- false_negative_intelligence_foundation
- aggregator_discovery_assessment
- aggregator_discovery_feedback_loop

Status:

HISTORICAL REVIEW

---

## REVIEW REQUIRED

The following areas require future reconciliation against the current architecture.

- source_capabilities
- source_evaluation
- source_strategy_review
- workspace terminology
- dashboard terminology

---

## Refactoring Rule

No code renaming should occur until terminology and architecture reconciliation are complete.


## Historical Terminology Reference

See:

- docs/archive/legacy/historical_terminology.md
