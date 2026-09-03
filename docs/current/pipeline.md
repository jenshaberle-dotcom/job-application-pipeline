# Pipeline State Machine

Status: current architecture contract  
Active product track: **PRODUCT-RECOVERY-001 / issue #783**

## Purpose

The project has two related state machines:

1. **Employer/source acquisition lifecycle** — how discovery becomes an approved controlled source.
2. **Concrete job product lifecycle** — how an observed vacancy becomes current, assessed, rankable, recommended and application-ready.

Local scripts must not invent product transitions outside these contracts.

## A. Employer/source acquisition lifecycle

| State | Meaning | Allowed next states | Automatic transition |
|---|---|---|---:|
| discovered | candidate observed by sensors or benchmark input | promotion_recommended, rejected_or_parked | yes |
| promotion_recommended | candidate deserves further inspection | origin_url_required, manual_review_required, rejected_or_parked | no |
| origin_url_required | candidate needs Employer-Origin URL discovery | origin_url_candidate_found, manual_review_required | yes |
| origin_url_candidate_found | bounded resolver selected a plausible origin | origin_url_validated, manual_review_required | no |
| origin_url_validated | origin URL has bounded/trusted validation | detail_evidence_required, connector_candidate | no |
| detail_evidence_required | concrete vacancy/detail proof required | detail_evidence_found, manual_review_required | yes |
| detail_evidence_found | concrete detail evidence available | connector_candidate, manual_review_required | no |
| connector_candidate | source is a plausible connector candidate | build_approval_required, manual_review_required | no |
| build_approval_required | connector artifact generation needs approval/standing authority | connector_artifact_generated, manual_review_required | no |
| connector_artifact_generated | generated artifacts exist for review | validation_required, manual_review_required | no |
| validation_required | connector behavior needs validation | approval_required, manual_review_required | no |
| approval_required | controlled-source activation decision required | active_controlled, manual_review_required | no |
| active_controlled | source is active under controlled operation | monitor, deactivation_review_required | no |
| manual_review_required | automatic path stopped | previous safe stage or rejected_or_parked | no |
| rejected_or_parked | candidate intentionally stopped | manual_review_required | no |

### Acquisition transition rules

- Discovery signal is never equivalent to source activation.
- Aggregator provenance may discover a candidate but never supplies final Product/Application action authority by itself.
- Automatic transitions may move only into bounded analysis/evidence-request states unless an approved standing authorization explicitly covers the transition.
- Connector registration and controlled activation remain distinct authorities.
- Reset/reprocess flows must identify exact targets before apply.
- Gate stops require reason, evidence class and next safe action.

## B. Concrete job Product V1 lifecycle

The current product-value pipeline is:

```text
observed
-> employer_origin_resolved
-> current_vacancy_verified
-> bronze_observed
-> silver_canonical
-> assessment_current
-> capability_fit_resolved
-> hard_filter_resolved
-> rankable
-> recommendation_eligible
-> application_ready
-> draft_for_review
```

### Product stages

| Stage | Required truth | Failure/unknown behavior |
|---|---|---|
| `observed` | market/source observation exists | remains historical discovery evidence |
| `employer_origin_resolved` | concrete Employer-Origin vacancy/action URL resolved | aggregator-only stays discovery-only |
| `current_vacancy_verified` | fresh exact vacancy evidence supports current activity | stale/closed/unverifiable is not actionable/recommended |
| `bronze_observed` | raw acquisition/lineage retained | no Product authority implied |
| `silver_canonical` | normalized canonical job exists | no current/ranking authority implied |
| `assessment_current` | assessment bound to current vacancy detail fingerprint | detail drift requires audited refresh |
| `capability_fit_resolved` | approved Candidate Facts support/deny required capability fit | missing evidence stays unknown/review-required |
| `hard_filter_resolved` | employment/language/hours/seniority and other approved hard filters resolved | failure excludes; required unknown blocks authoritative ranking |
| `rankable` | all required ranking components/evidence complete | no recommendation claim yet |
| `recommendation_eligible` | rankable + approved Top-5 policy, currently overall score >=70 | below threshold remains rankable but not Top-5 |
| `application_ready` | current Employer-Origin job plus approved candidate/job evidence available | generation blocked/fallback as defined by application contract |
| `draft_for_review` | coherent generated CV/letter package returned | never implies submit/send approval |

## Rankable is not Top-5

Current approved semantics:

```text
rankable
  = required Product V1 evidence complete enough to calculate authoritative scores

recommended / Top-5 eligible
  = rankable
    + no hard-filter blocker
    + approved minimum score >= 70
    + at most five highest-ranked qualifying jobs
```

The result is allowed to contain fewer than five jobs. The pipeline must never lower the threshold or silently promote below-threshold jobs to fill a quota.

## Freshness and detail drift

A previous observation or assessment is not sufficient evidence that a vacancy is current now.

Current implementation contract:

```text
live exact detail matches assessment fingerprint
    -> existing assessment may remain current

live exact detail differs
    -> detail_drift
    -> revisions-audited assessment refresh
    -> stale capability/ranking evidence reset as required
    -> capability/hard-filter/ranking gates rerun

explicit closure / dead detail
    -> not current/actionable/recommended
```

The exact long-term product policy for publication-age limits and ambiguous currentness remains governed by open product decisions, but **known stale/closed jobs must not survive as current recommendations**.

## Capability and hard-filter review

Current approved hard-filter families include:

- permanent employment requirement;
- accepted working languages German/English;
- 35–40 weekly-hours compatibility;
- capability/requirements fit taking precedence over title-only seniority.

Missing required evidence stays `manual_review_required`/unknown until resolved. Evidence-backed review may close a manual-review state only when bound to the current assessment/vacancy snapshot. It must not override deterministic failure evidence.

## Application transition

Application preparation is deliberately outside ranking authority.

```text
explicit operator Generate
-> load approved base CV/letter
-> load Candidate Facts
-> load exact current vacancy evidence
-> provider-backed structured draft when available
   or evidence-first fallback
-> validate grounding/package
-> render CV DOCX/PDF + letter DOCX/PDF + ZIP
-> draft_for_review
```

No stage above authorizes automatic submission, email send or silent application-state mutation.

## Current operational gap

DEMO-001 required separate bounded helpers for:

- live candidate scouting;
- detail-integrity checks;
- assessment refresh;
- capability-fit refill;
- hard-filter evidence closing;
- ranking persistence;
- operator smoke.

Those tools are valid recovery/diagnostic evidence, but they are **not the desired steady-state product pipeline**. PRODUCT-RECOVERY-001 must converge them into one normal, observable orchestration path while retaining fail-closed authority boundaries.

## Historical acquisition-control notes

CAND-001, STOP-002, REPAIR-001 and DIAG-001 remain valid retained acquisition/repair capabilities. They are no longer the complete story of the project and must be interpreted inside the broader product-value pipeline above.

Detailed stop taxonomy and repair strategy remain under `docs/reference/search-intelligence/stop_taxonomy_and_repair_registry.md`.
