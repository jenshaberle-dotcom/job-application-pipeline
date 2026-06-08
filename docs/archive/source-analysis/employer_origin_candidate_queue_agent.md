# Employer-Origin Candidate Queue Agent

## Status

Implemented as S2Z candidate workflow.

## Purpose

The candidate queue agent gives the employer-origin workflow an operator-facing queue.

It reads PostgreSQL-backed employer-origin candidates and gate reviews, classifies the next safe action per candidate and prints actionable commands. It does not execute child agents.

## Boundary

The queue agent does not:

- bypass gates
- write database state
- activate sources
- write Bronze rows
- generate connectors
- enable recurring ingestion
- use CSV/Excel/export artifacts as inputs

It is a DB-backed queue and prioritization view only.

## Priority Model

The queue prioritizes:

1. active controlled sources without passed lifecycle tracking
2. S4A connector artifact dry-run candidates
3. S4A connector-build-readiness checks
4. connector-candidate gate evaluation
5. detail-evidence repair when explicitly allowed
6. manual-review stops

## Example

```bash
python -m scripts.run_employer_origin_candidate_queue_agent \
  --target-location hannover \
  --reviewed-by jens \
  --allow-repair \
  --print-next-command
```

## Interpretation

S2Z makes the agent workflow easier to operate without turning it into uncontrolled automation. It still requires the operator to execute the printed command and review the resulting DB-backed gate state.

## Completed Active Sources

A candidate with status `active_controlled`, a passed `source_lifecycle_tracking` gate and no blocked or manual-review gates is treated as completed for the connector-building queue.

The queue reports `monitor_source_lifecycle` and does not print a connector artifact generation command. This prevents already-active sources such as Finanz Informatik from being presented as if connector implementation were still the next action.

## Repair Loop Safety

When bounded detail-evidence repair has already been attempted and the gate stop reason states that no concrete detail pages with profile and target/remote signals were found, the queue does not propose the same repair again.

The candidate is shown as `manual_review_stop` with no command. This prevents the operator loop from repeatedly running a known exhausted repair path.


## S4D Queue Progression

The queue now carries gate `evidence` into the shared chain decision logic. This is required because S4A artifact readiness depends on concrete detail URLs stored in `connector_candidate_gate.evidence.connector_candidate_spec`. Without that evidence, the queue could only see status/decision labels and would repeatedly underrate candidates that were actually artifact-ready.

Queue classification also follows the post-artifact sequence:

1. missing or blocked detail evidence -> repair/manual-review path
2. incomplete S4A readiness -> build-readiness agent
3. S4A ready but artifact files missing -> connector artifact generator
4. artifacts present but validation not passed -> S4B connector validation
5. validation passed but approval missing -> explicit approval stop
6. final approval passed -> non-activating registration execution plan

The queue intentionally does not provide approval tokens and therefore cannot silently approve connector registration.

## S4E Update: Recheck Semantics for Suppressed Aggregator Candidates

Known candidates that are suppressed from aggregator discovery are not forgotten. The queue now has a shared policy hook for recheck eligibility. This keeps aggregator suppression separate from candidate lifecycle management.

A candidate can become recheck-eligible when all of the following are true:

- it has no active controlled connector
- its status is part of the inactive candidate lifecycle, for example `candidate`, `discovery`, `deferred`, `manual_review_required`, `connector_candidate`, `watchlist` or `degraded`
- its latest gate or stop reason is recheckable, for example missing or unclear fachliche/professional relevance, missing detail evidence, temporary lack of matching jobs or temporary technical reachability problems
- it was not reviewed recently according to the shared policy interval

Hard-stop states such as `deprecated`, `disabled` and `abort_documented` are not automatically rechecked. Blocked risk level is also not automatically rechecked.

Queue action:

```text
run_employer_origin_recheck
```

This action intentionally routes through the existing bounded employer-origin agent chain instead of reviving the aggregator path.

