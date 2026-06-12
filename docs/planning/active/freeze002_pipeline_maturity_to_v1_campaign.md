# FREEZE-002 Pipeline Maturity to V1 Campaign

Status: planned campaign  
Type: second freeze campaign / V1 maturity path  
Boundary: planning anchor, not an apply-capable pipeline change

## Purpose

FREEZE-002 raises the remaining pipeline areas toward >=90% target maturity
without derailing the usable V1 route. It follows the current GENERIC/EXPAND
work and keeps GUI-enabled job review on the critical path.

## Position in the roadmap

Required sequence:

1. Close the current GENERIC/EXPAND stop-control and evidence blockers.
2. Prove a minimal controlled V1 job-review path with GUI.
3. Run FREEZE-002 to lift weak but necessary pipeline areas toward >=90%.
4. Run REFACTOR-001 before cloud, outbox, Kafka, Spark or serious production.

This campaign must not move cloud or streaming earlier. It prepares them by
making the local/batch system mature, observable and maintainable first.

## Maturity targets

| Area | Target | Notes |
|---|---:|---|
| Generic evidence and stops | >=90 | No candidate apply without defensible evidence. |
| Review Queue and GUI actionability | >=90 | V1 must be usable by the operator, not only scripts. |
| Search Intelligence closure | >=90 | Discovery loops must explain stops and next actions. |
| Scheduler and operations | >=90 | Runs, failures and reruns must be visible and bounded. |
| Source/origin evidence | >=90 | Employer-origin evidence must beat one-off manual fixes. |
| Connector readiness | >=90 | Artifact generation, validation and activation stay gated. |
| Defect management baseline | >=90 | Defect classes and ownership must be explicit. |
| Governance/compliance auditability | >=90 | Decisions must remain reviewable and reproducible. |

## Work lanes

FREEZE-002 may bundle independent horizontal work when impact analysis shows no
hidden coupling. Vertical decision logic remains separate.

Allowed horizontal lanes:

- maturity scorecards and blocker snapshots,
- read-only Review Queue or Control Center improvements,
- defect taxonomy and report foundations,
- scheduler/operations diagnostics,
- documentation/governance alignment,
- source and connector health read models.

Separate PRs or explicit justification are required for:

- candidate or gate mutation,
- connector activation,
- scheduler behavior changes,
- source-learning or promotion logic changes,
- Bronze/Silver/Gold writes,
- external request expansion,
- any CSV/export artifact used as pipeline input.

## Exit criteria

