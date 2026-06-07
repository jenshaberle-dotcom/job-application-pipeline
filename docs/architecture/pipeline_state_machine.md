# Pipeline State Machine

Status: active architecture contract
Scope: employer-origin candidate lifecycle and Search Intelligence transitions

## Purpose

The pipeline needs one lifecycle truth. Local scripts must not invent new state transitions without updating this contract.

## Candidate lifecycle

| State | Meaning | Allowed next states | Automatic transition |
|---|---|---|---:|
| discovered | candidate was observed by sensors or benchmark input | promotion_recommended, rejected_or_parked | yes |
| promotion_recommended | Türsteher recommends further inspection | origin_url_required, manual_review_required, rejected_or_parked | no |
| origin_url_required | candidate needs source URL discovery | origin_url_candidate_found, manual_review_required | yes |
| origin_url_candidate_found | URL Finder selected a plausible URL | origin_url_validated, manual_review_required | no |
| origin_url_validated | bounded probe or trusted evidence validated origin URL | detail_evidence_required, connector_candidate | no |
| detail_evidence_required | concrete job/detail evidence is needed | detail_evidence_found, manual_review_required | yes |
| detail_evidence_found | detail evidence is available | connector_candidate, manual_review_required | no |
| connector_candidate | source is a plausible connector candidate | build_approval_required, manual_review_required | no |
| build_approval_required | connector artifact generation needs approval | connector_artifact_generated, manual_review_required | no |
| connector_artifact_generated | generated artifacts exist for review | validation_required, manual_review_required | no |
| validation_required | connector behavior needs validation | approval_required, manual_review_required | no |
| approval_required | source activation decision is required | active_controlled, manual_review_required | no |
| active_controlled | source is active under controlled operation | monitor, deactivation_review_required | no |
| manual_review_required | automatic path stopped | previous safe stage or rejected_or_parked | no |
| rejected_or_parked | candidate intentionally stopped | manual_review_required | no |

## Transition rules

- Automatic transitions may only move into analysis or evidence-request states.
- Any transition into active_controlled requires manual approval.
- Any transition affecting active_controlled entities requires explicit opt-in.
- Reset and reprocess flows must show selected targets before apply.
- Gate stops must include next_safe_action and stop_reason.

<!-- BEGIN CAND-001-STATE-TRANSITION -->
## CAND-001 State Transition

CAND-001 operationalizes the transition:

    origin_url_candidate_found -> origin_url_validated

for candidates where a live bounded URL-Finder run selected an A/B-tier origin URL and `candidate_url` is empty.

The transition is SZ1_CANDIDATE_METADATA and requires dry-run, explicit apply and audit review.
<!-- END CAND-001-STATE-TRANSITION -->
