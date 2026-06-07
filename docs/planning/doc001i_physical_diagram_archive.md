# DOC-001I Physical Diagram Archive Pass

Status: implemented documentation build log
Scope: first safe physical archive move after DOC-001G/H

## Purpose

DOC-001I performs the first physical archive move in the documentation rebaseline.

The goal is intentionally small: move only the old `docs/diagrams/` pages after
DOC-001G and DOC-001H created current replacements.

## Archived content

| Old path | New archive path | Current replacement |
|---|---|---|
| `docs/diagrams/architecture.md` | `docs/archive/diagrams/architecture.md` | `docs/architecture/system_diagrams.md` |
| `docs/diagrams/bronze_data_model.md` | `docs/archive/diagrams/bronze_data_model.md` | `docs/database/schema_relationships.md` |

## Why this is safe

- The old connector architecture diagram is superseded by the Search
  Intelligence control-surface diagrams.
- The old Bronze/Silver data model diagram is superseded by the database
  relationship map.
- The archive directory keeps historical content available.
- Navigation and tests now point to the Current Truth replacements.

## What this deliberately does not do

DOC-001I does not mass-move `docs/planning/` or `docs/source_analysis/`.
Those directories are much larger and have more historical links, test anchors
and handover references. They should be moved only after a dedicated reference
check exists.

## Next archive candidate

The next archive block should create a simple link/reference check and then move
or mark a small batch of stale planning/source-analysis files with low contract
risk.
