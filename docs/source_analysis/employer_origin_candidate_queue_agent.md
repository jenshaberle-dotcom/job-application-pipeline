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
