# Documentation Path Status and Archive Triage

Status: current archive/deprecation control surface
Scope: DOC-001I docs-path cleanup and physical-archive decision rules

## Purpose

The docs tree still contains a large historical surface, but DOC-001 now has a
small Current Truth reader path and a first physical archive move.

This page explains which paths are current, reference, historical, transitional
or archived.

## Current path classes

| Path | DOC-001I status | Reader instruction |
|---|---|---|
| `README.md` | Current Truth entry | Start here for project motivation and positioning. |
| `docs/README.md` | Current Truth entry | Start here for documentation navigation. |
| `docs/architecture/` | Mixed but controlled | Use `README.md`, `current_system_overview.md`, `system_diagrams.md`, and `architecture_document_status.md` first. |
| `docs/database/` | Current reference, rebaselined | Use `README.md`, `schema_overview.md`, and `schema_relationships.md` before old table details. |
| `docs/governance/` | Current governance/control surface | Use for agent registry, capability audit, drift guard and ADR rebaseline controls. |
| `docs/operations/` | Current operator surface | Use for runbook, migration tracking and scheduler/watchdog notes. |
| `docs/design/` | Current reference | Keep for Deep Ocean visual identity and documentation rules. |
| `docs/data_sources/` | Current/reference mixed | Keep as connector/source contract reference. |
| `docs/observability/` | Current/reference mixed | Keep as source health and monitoring reference. |
| `docs/classification/`, `docs/relevance/` | Reference | Keep as domain references; not the main architecture story. |
| `docs/planning/` | Historical by default | Build logs and planning notes. Do not read as Current Truth unless explicitly promoted. |
| `docs/source_analysis/` | Historical by default | Source-analysis traceability. Do not read as Current Truth unless explicitly promoted. |
| `docs/archive/diagrams/` | Archived historical diagrams | Preserved for traceability only; use current replacements. |
| `docs/project_state/` | Transitional handover/state surface | Useful for chat/runtime handover, but not stable architecture truth. |

## Completed physical archive moves

| DOC block | Old path | New archive path | Current replacement |
|---|---|---|---|
| DOC-001I | `docs/diagrams/architecture.md` | `docs/archive/diagrams/architecture.md` | `docs/architecture/system_diagrams.md` |
| DOC-001I | `docs/diagrams/bronze_data_model.md` | `docs/archive/diagrams/bronze_data_model.md` | `docs/database/schema_relationships.md` |

## Why not move everything immediately?

A mass move of planning/source-analysis files would reduce visual clutter, but it
also risks breaking historical links, tests, and prior handover references.

DOC-001 therefore separates three actions:

1. **Declare status**: make it obvious what is Current Truth, Reference,
   Historical or Archived.
2. **Index historical content**: keep it searchable without pretending it is
   current architecture.
3. **Move only with a link check**: physically archive files once navigation and
   tests have been updated.

## Archive candidate queue

The following paths remain archive candidates after the completed DOC-001I diagram move.

## Remaining physical archive candidates

| Priority | Candidate | Intended action |
|---|---|---|
| 1 | stale planning documents not referenced by contract tests | Move under `docs/archive/planning/` or keep indexed with historical banner. |
| 2 | stale source-analysis documents not referenced by active source work | Move under `docs/archive/source_analysis/` or keep indexed with historical banner. |
| 3 | obsolete architecture narratives after ADR/status review | Replace with Current Truth extracts or move to archive/reference. |
| 4 | transitional `docs/project_state/` snapshots | Keep only if they support current handover/state workflows. |

## Archive decision rule

Move a historical document only when all are true:

- it is not part of the Current Truth reader path,
- it is not an active governance/contract anchor,
- links and tests have been checked,
- a redirect/index entry remains,
- the move does not hide information needed for the next implementation block.

## DOC-001J reference guard

DOC-001J adds `scripts/check_documentation_references.py` as the lightweight
reference/link check before any larger physical move of planning or
source-analysis documents.

The guard must stay green before a larger move. It treats retired `docs/diagrams/`
paths as historical archive-map references, and treats `docs/archive/planning/`
and `docs/archive/source_analysis/` as planned future archive targets rather than
current directories.

Operator command:

```bash
python scripts/check_documentation_references.py --write-report --json
```

Expected archive-readiness result: `unresolved_count=0`.
