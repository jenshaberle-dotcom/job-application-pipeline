# Job Application Pipeline Research State

Status: knowledge decision-mode projection
Last reviewed: 2026-08-30
Portfolio contract: `Data-Retention-Janitor/docs/contracts/KNOWLEDGE-RESEARCH-LAYER-v1.md`
Project activity authority: `PROJECT-REENTRY.json` -> `docs/current/README.md`

## Operating state

- mode: `execution`
- research_required: `false`
- research_reason: none
- current_research: none

This file owns Knowledge/Research decision state only. It does not declare whether the project is dormant, active, blocked or at safe stop; project activity and next-action truth are resolved through `PROJECT-REENTRY.json` and the canonical current-truth surface on `main`.

## Accepted knowledge

- Outcome-oriented execution remains primary.
- Continue execution without a new research loop while work stays inside the already-decided solution space.
- Before a material directional change not covered by accepted project knowledge, perform focused internal + external research and choose `REUSE`, `ADOPT`, `EXTEND` or `BUILD`.

## Rejected approaches

- Mandatory research before every implementation step: rejected as unnecessary process overhead.
- Research only at kickoff: rejected because material direction changes can occur during an existing mission.
- Using Knowledge/Research state as project activity or work-admission authority: rejected because Re-Entry/current truth owns activity/continuation truth.

## Open knowledge gaps

None created by this projection. Add only gaps tied to a concrete outcome or directional decision.

## Research records

Create focused records under `docs/knowledge/research/YYYY-MM-DD-<topic>.md`. Preserve rejected alternatives and their reasons. Promote durable architectural decisions into the repository's existing decision/ADR mechanism where appropriate.
