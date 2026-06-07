# Planning Documents

Status: historical build-log area by default
Scope: DOC-001C documentation navigation

## Important

Documents in this directory are historical by default.

They may contain valuable reasoning, decisions, and implementation context, but
they are not automatically current architecture truth.

For current system understanding, start with:

- `docs/README.md`
- `docs/architecture/current_system_overview.md`
- `docs/architecture/system_diagrams.md`
- `docs/governance/README.md`

## Promotion rule

A planning document may influence Current Truth only when its content is
explicitly promoted into one of the active documents, such as:

- architecture overview,
- governance registry,
- capability audit,
- ADR,
- operator runbook,
- current documentation map.

## Why this matters

The project moved quickly. Many planning files describe a specific build step,
bug fix, experiment, or milestone. Treating all of them as current system docs
creates documentation drift.

## DOC-001 policy

DOC-001 may later archive, index, or deprecate individual planning documents.
Until then, this directory remains traceability first, not reader entry point.
