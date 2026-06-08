# Documentation

Status: current documentation entry point
Scope: DOC-001L information architecture

## Purpose

This directory is intentionally small at the top level. It separates current
truth, practical guides, reference material, decisions, active planning, and
history so a reader does not have to excavate old build notes to understand the
project.

## Read this first

1. `current/product.md`
2. `current/architecture.md`
3. `current/pipeline.md`
4. `current/system-diagrams.md`
5. `current/governance.md`
6. `current/operations.md`

## Structure

| Area | Purpose | Rule |
|---|---|---|
| `current/` | Short, curated truth about the current product and architecture. | Keep small; promote only stable facts. |
| `guides/` | How-to documentation for development, operation and testing. | Practical instructions live here, not in the root README. |
| `reference/` | Detailed lookup material: database, agents, governance, sources, security, scoring and glossary. | Precise detail is welcome, but not the main story. |
| `decisions/` | ADRs and their DOC-001 status surface. | Decisions are traceability, not general reference prose. |
| `planning/` | Active planning only. | Old work-item notes belong in `archive/planning/`. |
| `archive/` | Historical build notes, old analyses, reviews and replaced diagrams. | Useful for traceability, not authoritative current truth. |

## Artifact rule

The documentation architecture applies to files, not only folders:

- current docs should be few, maintained and readable;
- reference docs should explain stable concepts or contracts;
- planning docs should be active and short-lived;
- historical work-item traces should be archived instead of half-promoted;
- exports and handover files must not become source-of-truth documentation.

The project uses docs-as-code guards for this:

- `scripts/check_documentation_architecture.py`
- `scripts/check_documentation_references.py`
- `scripts/check_adr_rebaseline.py`

## Key reference surfaces

- `reference/database/schema_overview.md`
- `reference/database/schema_relationships.md`
- `reference/governance/governance_foundation.md`
- `reference/security/search_intelligence_security_baseline.md`
- `decisions/adr_status_table.md`

## ADRs

ADRs live in `decisions/adr/`. Use `decisions/adr_status_table.md` before
reading an ADR as current implementation truth.

## Exports

`exports/` contains generated runtime reports and review artifacts. Exports are
reports, not source-of-truth handoffs and not pipeline inputs.

Reference path anchors: `docs/reference/database/schema_overview.md`, `docs/reference/database/schema_relationships.md`.
