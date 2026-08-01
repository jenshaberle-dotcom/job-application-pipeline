# Product Acceptance Scenarios

Status: scenario inventory — expectations require operator approval
Owner: Jens

## Purpose

Product fidelity is demonstrated through representative outcomes, not only prose and technical tests.

A scenario becomes authoritative only after its expected behavior is approved by the operator. Until then it is a test-design placeholder and must not be used to infer product semantics.

## Scenario contract

Every approved scenario must define:

- given market/job/employer evidence;
- expected inclusion or exclusion;
- expected queue or lane;
- expected rank or rank constraints where relevant;
- required visible reasons;
- required uncertainty/missing-data indicators;
- allowed operator actions;
- forbidden automatic actions;
- stable identifiers for automated fixtures.

## Required scenario inventory

| Scenario ID | Decision state | Product ambiguity covered |
|---|---|---|
| `PA-001-five-strong-jobs` | open_operator_decision | Desired behavior when at least five high-quality jobs qualify. |
| `PA-002-fewer-than-five-qualified` | open_operator_decision | Whether the product returns fewer results or fills the set with weaker jobs. |
| `PA-003-aggregator-without-origin` | open_operator_decision | Treatment of a detailed aggregator result without confirmed origin source. |
| `PA-004-employer-without-active-job` | open_operator_decision | Separation between employer observation and concrete job review. |
| `PA-005-duplicate-across-platforms` | open_operator_decision | Canonical job and source-family behavior. |
| `PA-006-stale-official-posting` | open_operator_decision | Freshness versus official-source trust. |
| `PA-007-unknown-publication-date` | open_operator_decision | Missing-date handling. |
| `PA-008-strong-keywords-wrong-work` | open_operator_decision | Semantic task mismatch despite title/keyword overlap. |
| `PA-009-adjacent-role-high-interest` | open_operator_decision | Adjacent role families and primary queue eligibility. |
| `PA-010-location-mismatch` | open_operator_decision | Strong role fit but unacceptable location/office expectation. |
| `PA-011-unclear-remote-model` | open_operator_decision | Unknown or conflicting remote evidence. |
| `PA-012-experience-requirement-gap` | open_operator_decision | Handling of unsupported seniority/experience expectations. |
| `PA-013-missing-salary` | open_operator_decision | Salary-data absence. |
| `PA-014-already-rejected-job` | open_operator_decision | Repeat suppression and resurfacing. |
| `PA-015-job-materially-changed` | open_operator_decision | Resurfacing after significant evidence or content change. |
| `PA-016-multiple-jobs-one-employer` | open_operator_decision | Queue diversity versus best opportunities at one employer. |
| `PA-017-identity-ambiguity` | open_operator_decision | Employer/entity uncertainty. |
| `PA-018-conflicting-source-evidence` | open_operator_decision | Conflicting status, location or detail across sources. |
| `PA-019-provider-only-evidence` | open_operator_decision | Provider/LLM evidence without deterministic confirmation. |
| `PA-020-hard-filter-failure` | open_operator_decision | Whether and where an otherwise attractive but disqualified job appears. |
| `PA-021-insufficient-market-results` | open_operator_decision | Honest empty/low-volume cycle behavior. |
| `PA-022-ranking-tie` | open_operator_decision | Tie-breaking and explanation. |
| `PA-023-ranking-change-between-cycles` | open_operator_decision | Change explanation and operator trust. |
| `PA-024-review-action-retry` | open_operator_decision | Idempotency and visible failure for operator actions. |
| `PA-025-application-prohibited` | approved | No automatic application submission under any ranking outcome. |

## Example structure

The following is a format example only. Its expected values are not approved product truth.

```yaml
scenario_id: PA-002-fewer-than-five-qualified
status: open_operator_decision
given:
  observed_jobs: 12
  jobs_meeting_approved_threshold: 2
expect:
  primary_queue_count: pending_operator_decision
  explanation: pending_operator_decision
  uncertainty_display: pending_operator_decision
allowed_actions: pending_operator_decision
forbidden_actions:
  - auto_apply
```

## Approval and implementation

1. Resolve the linked product decisions.
2. Record the operator-approved expected outcome.
3. Add deterministic fixtures where feasible.
4. Map backlog stories to scenario IDs.
5. Run automated conformance tests.
6. Complete a real operator smoke for visible behavior.

Automated tests may prove scenario conformance. Only the operator can approve whether the scenario itself represents the desired product.
