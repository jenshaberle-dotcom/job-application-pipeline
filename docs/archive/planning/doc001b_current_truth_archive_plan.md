# DOC-001B Current Truth and Archive Plan

Status: implemented as documentation rebaseline planning block  
Scope: current truth, diagrams, archive/deprecation, ADR rebaseline

## Intent

DOC-001B moves from inventory to structure.

It defines:

- the current system overview entry point,
- current system diagrams,
- archive/deprecation policy,
- ADR rebaseline plan.

## Implemented artifacts

- `docs/current/architecture.md`
- `docs/current/system-diagrams.md`
- `docs/reference/governance/documentation_archive_deprecation_plan.md`
- `docs/decisions/adr_rebaseline_plan.md`

## Boundary

- documentation only
- no file moves
- no archive operation yet
- no database access
- no pipeline execution
- no source/connector/scheduler changes

## Why no file moves yet

The documentation surface is too large to move safely before the reduced Current
Truth layer is stable.

DOC-001B therefore adds the target structure and rules first. Later DOC-001 blocks
can deprecate, index, or move historical docs with less risk.

## Follow-up

Recommended next DOC-001 blocks:

1. DOC-001C: README and operator navigation rebaseline.
2. DOC-001D: ADR status table.
3. DOC-001E: archive/deprecation index for planning and source-analysis docs.
4. DOC-001F: architecture docs consolidation and old-diagram cleanup.
