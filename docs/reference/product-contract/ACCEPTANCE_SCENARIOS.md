# Product Acceptance Scenarios

Status: active scenario authority  
Owner: Jens

## Purpose

Product fidelity is demonstrated through representative outcomes, not only prose and technical tests.

A scenario is authoritative only when its expected behavior is approved by the operator or is a direct conformance projection of already approved product decisions.

## Scenario contract

Every approved scenario defines:

- given market/job/employer evidence;
- expected inclusion/exclusion;
- expected queue/lane;
- expected rank/rank constraints where relevant;
- required visible reasons;
- required uncertainty/missing-data indicators;
- allowed operator actions;
- forbidden automatic actions;
- stable identifiers for automated fixtures where feasible.

## Current scenario inventory

| Scenario ID | Decision state | Current expected behavior |
|---|---|---|
| `PA-001-five-strong-jobs` | approved | When at least five current Employer-Origin jobs pass all required evidence/hard-filter gates and each meets the approved >=70 recommendation threshold, the primary queue contains the best **at most five** under the approved ranking policy. |
| `PA-002-fewer-than-five-qualified` | approved | When fewer than five jobs meet the approved recommendation contract, return fewer than five. Never fill with below-threshold, blocked or insufficiently evidenced jobs. |
| `PA-003-aggregator-without-origin` | approved | Aggregator-only jobs remain discovery evidence. They cannot be Top-5/Application action targets until a current Employer-Origin vacancy or approved equivalent origin path is resolved. |
| `PA-004-employer-without-active-job` | open_operator_decision | Separation between employer observation and concrete job review outside current recommended jobs. |
| `PA-005-duplicate-across-platforms` | open_operator_decision | Canonical job and source-family behavior. |
| `PA-006-stale-official-posting` | approved | A vacancy known to be closed/stale/dead on its action-authority path must leave current/actionable/recommended state. Historical observation/lineage may remain visible. Ambiguous currentness without decisive evidence stays governed by PD-042. |
| `PA-007-unknown-publication-date` | open_operator_decision | Missing-date handling. |
| `PA-008-strong-keywords-wrong-work` | open_operator_decision | Semantic task mismatch despite title/keyword overlap. |
| `PA-009-adjacent-role-high-interest` | open_operator_decision | Adjacent role families and primary queue eligibility. |
| `PA-010-location-mismatch` | open_operator_decision | Strong role fit but unacceptable location/office expectation. |
| `PA-011-unclear-remote-model` | open_operator_decision | Unknown/conflicting remote evidence. |
| `PA-012-experience-requirement-gap` | approved | Advertised seniority label alone does not decide. Actual requirements/capability evidence govern; unsupported capability requirements fail and missing evidence remains review-required. |
| `PA-013-missing-salary` | approved | Missing salary does not hard-fail an otherwise eligible job; salary remains a soft signal. |
| `PA-014-already-rejected-job` | open_operator_decision | Repeat suppression/resurfacing. |
| `PA-015-job-materially-changed` | open_operator_decision | Product resurfacing semantics after material evidence/content change. Technical stale assessment evidence must already be refreshed before current ranking reuse. |
| `PA-016-multiple-jobs-one-employer` | open_operator_decision | Queue diversity versus best opportunities at one employer. |
| `PA-017-identity-ambiguity` | open_operator_decision | Employer/entity uncertainty. |
| `PA-018-conflicting-source-evidence` | open_operator_decision | Conflicting status/location/detail across sources. |
| `PA-019-provider-only-evidence` | approved | Provider-generated text/evidence cannot create Candidate Facts, current-vacancy truth, ranking authority, application approval or submit/send authority. Deterministic/product-approved factual sources remain authoritative. |
| `PA-020-hard-filter-failure` | approved | A hard-filter failure never enters authoritative Top-5. Required unknown evidence remains review-required, not silently passed/failed. |
| `PA-021-insufficient-market-results` | approved | Honest low-volume output is valid. The system does not fabricate or lower the recommendation contract merely to display five jobs. |
| `PA-022-ranking-tie` | approved | Jobs within the approved 3-point comparison window may be reordered only by the approved hybrid/commute/public-transport preference signals; explanation remains visible. |
| `PA-023-ranking-change-between-cycles` | open_operator_decision | Change explanation and operator trust. |
| `PA-024-review-action-retry` | open_operator_decision | Idempotency/visible failure for operator actions. |
| `PA-025-application-prohibited` | approved | No automatic application submission or send under any ranking/application outcome. |
| `PA-026-explicit-application-generation` | approved | Only explicit operator Generate may trigger application provider drafting. Approved base CV/letter text may be provider structure/style context; Candidate Facts/exact vacancy remain factual authority. Output is CV/letter review artifacts, never submission authority. |
| `PA-027-product-recovery-cold-flow` | approved | Product Recovery acceptance uses one normal observable discovery-to-application path. In a controlled acceptance campaign containing at least five qualifying current Employer-Origin jobs, the flow should surface >=5 jobs satisfying the approved recommendation contract and produce a selected-job application package requiring only small edits. If the real market contains fewer qualifying jobs, truthful fewer-than-five behavior from PA-002 remains correct. |

## Approved scenario details

### PA-001 — five strong jobs

```yaml
scenario_id: PA-001-five-strong-jobs
status: approved
given:
  current_employer_origin_jobs_meeting_required_evidence_and_hard_filters: 7
  jobs_scoring_at_least_70: 6
expect:
  primary_queue_count: 5
  queue_membership: highest-ranked qualifying five
  reasons_visible: true
  uncertainty_visible: true
forbidden:
  - below_threshold_fill
  - aggregator_only_action_url
  - hidden_hard_filter_override
```

### PA-002 — fewer than five qualified

```yaml
scenario_id: PA-002-fewer-than-five-qualified
status: approved
given:
  current_employer_origin_jobs_meeting_required_evidence_and_hard_filters: 6
  jobs_scoring_at_least_70: 1
expect:
  primary_queue_count: 1
  explanation: fewer_than_five_meet_approved_threshold
forbidden:
  - lower_threshold_for_quota
  - promote_rankable_below_threshold_to_top5
  - fabricate_jobs
```

This scenario reflects the important distinction exposed by DEMO-001: local runtime evidence may contain several `rankable` jobs while only a smaller number are recommendation-eligible under PD-051.

### PA-003 — aggregator discovery without Employer Origin

```yaml
scenario_id: PA-003-aggregator-without-origin
status: approved
given:
  discovery_source: stepstone_or_ba_or_other_aggregator
  employer_origin_vacancy: unresolved
expect:
  discovery_visible: allowed
  product_actionable: false
  top5_eligible: false
  application_ready: false
required_visible_reason: employer_origin_resolution_required
```

### PA-006 — known stale/closed vacancy

```yaml
scenario_id: PA-006-stale-official-posting
status: approved
given:
  previously_observed_job: true
  employer_origin_action_path: known_closed_or_dead
expect:
  historical_observation_preserved: true
  current_actionable: false
  recommendation_eligible: false
  application_ready: false
```

### PA-019 — provider-only claim

```yaml
scenario_id: PA-019-provider-only-evidence
status: approved
given:
  provider_output_contains_candidate_claim_not_in_candidate_facts: true
expect:
  claim_authoritative: false
  package_acceptance: fail_closed_or_remove_unsupported_claim
forbidden:
  - create_candidate_fact_from_provider_output
  - grant_ranking_authority
  - grant_submission_authority
```

### PA-026 — explicit application generation

```yaml
scenario_id: PA-026-explicit-application-generation
status: approved
given:
  operator_action: Generate application
  approved_base_cv: present
  approved_base_letter: present
  candidate_facts: present
  exact_current_vacancy_evidence: present
expect:
  provider_call: allowed_under_configured_boundary
  base_document_text_as_style_structure_context: allowed
  output_state: draft_for_review
  downloadable_package:
    - cv_docx
    - cv_pdf
    - letter_docx
    - letter_pdf
    - zip
forbidden:
  - auto_submit
  - auto_send
  - invent_candidate_fact
```

### PA-027 — Product Recovery cold flow

```yaml
scenario_id: PA-027-product-recovery-cold-flow
status: approved
given:
  controlled_market_or_fixture_contains_at_least_five_jobs_meeting_approved_contract: true
expect:
  one_normal_observable_flow: true
  manual_repair_campaign_between_normal_stages: false
  recommended_jobs_minimum: 5
  recommendation_threshold: 70
  aggregator_final_action_links: 0
  known_stale_recommendations: 0
  selected_application_package_requires_only_small_edits: true
forbidden:
  - demo_only_rows
  - fabricated_freshness
  - below_threshold_fill
  - ranking_override_for_quota
```

## Approval and implementation

1. Resolve linked open product decisions where the scenario depends on them.
2. Keep approved expected behavior in this file.
3. Add deterministic fixtures/contract tests where feasible.
4. Map Product Recovery stories to scenario IDs.
5. Run technical/contract conformance tests.
6. Complete real operator smoke/visual review where live/runtime behavior is part of acceptance.

Automated tests prove conformance. Only the operator can approve whether the scenario represents the intended product.
