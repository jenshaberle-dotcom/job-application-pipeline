# Documentation Path Status and Archive Triage

Status: current archive/deprecation control surface
Scope: DOC-001H docs-path cleanup and physical-archive decision rules

## Purpose

The docs tree still looks chaotic because DOC-001 deliberately rebuilt the
Current Truth reader path before moving large numbers of historical files.

This document makes the next archive rule explicit: historical content should be
visible as historical now, and moved only when link/test impact is understood.

## Current path classes

| Path | DOC-001H status | Reader instruction |
|---|---|---|
| `README.md` | Current Truth entry | Start here for project motivation and positioning. |
| `docs/README.md` | Current Truth entry | Start here for documentation navigation. |
| `docs/architecture/` | Mixed but controlled | Use `README.md`, `current_system_overview.md`, `system_diagrams.md`, and the architecture authority/status page first. |
| `docs/database/` | Current reference, now rebaselined | Use `README.md`, `schema_overview.md`, and `schema_relationships.md` before old table details. |
| `docs/governance/` | Current governance/control surface | Use for agent registry, capability audit, drift guard and ADR rebaseline controls. |
| `docs/operations/` | Current operator surface | Use for runbook, migration tracking and scheduler/watchdog notes. |
| `docs/design/` | Current reference | Keep for Deep Ocean visual identity and documentation rules. |
| `docs/data_sources/` | Current/reference mixed | Keep as connector/source contract reference. |
| `docs/observability/` | Current/reference mixed | Keep as source health and monitoring reference. |
| `docs/classification/`, `docs/relevance/` | Reference | Keep as domain references; not the main architecture story. |
| `docs/planning/` | Historical by default | Build logs and planning notes. Do not read as Current Truth unless explicitly promoted. |
| `docs/source_analysis/` | Historical by default | Source-analysis traceability. Do not read as Current Truth unless explicitly promoted. |
| `docs/diagrams/` | Archive candidate | Older diagram pages should be compared against `docs/architecture/system_diagrams.md`. |
| `docs/project_state/` | Transitional handover/state surface | Useful for chat/runtime handover, but not stable architecture truth. |

## Why not move everything immediately?

A mass move of planning/source-analysis files would reduce visual clutter, but it
also risks breaking historical links, tests, and prior handover references.

DOC-001H therefore separates three actions:

1. **Declare status**: make it obvious what is Current Truth, Reference,
   Historical or Archive Candidate.
2. **Index historical content**: keep it searchable without pretending it is
   current architecture.
3. **Move only with a link check**: physically archive files once navigation and
   tests have been updated.

## Physical archive candidates

| Priority | Candidate | Intended action |
|---|---|---|
| 1 | `docs/diagrams/architecture.md` | Compare against `docs/architecture/system_diagrams.md`; then move or replace with redirect note. |
| 2 | `docs/diagrams/bronze_data_model.md` | Compare against `docs/database/schema_relationships.md`; then move or replace with redirect note. |
| 3 | stale planning documents not referenced by contract tests | Move under `docs/archive/planning/` or keep indexed with historical banner. |
| 4 | stale source-analysis documents not referenced by active source work | Move under `docs/archive/source_analysis/` or keep indexed with historical banner. |

## Archive decision rule

Move a historical document only when all are true:

- it is not part of the Current Truth reader path,
- it is not an active governance/contract anchor,
- links and tests have been checked,
- a redirect/index entry remains,
- the move does not hide information needed for the next implementation block.

## Next archive block

DOC-001I should perform the first physical archive pass. It should start with the
small `docs/diagrams/` directory because the replacement diagrams already exist
in `docs/architecture/system_diagrams.md`.

The large `docs/planning/` and `docs/source_analysis/` moves should wait until a
simple link/reference check exists.
