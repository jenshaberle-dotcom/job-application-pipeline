# DOC-001A Documentation Rebaseline Inventory

Status: implemented as read-only inventory foundation  
Scope: documentation classification and ADR rebaseline intake

## Intent

DOC-001A starts the documentation rebaseline campaign with a read-only inventory.
It does not rewrite or archive documents yet.

## Implemented artifacts

- `scripts/inspect_documentation_rebaseline.py`
- `tests/test_documentation_rebaseline_inspection.py`
- `docs/governance/documentation_rebaseline_strategy.md`
- `docs/architecture/current_truth_documentation_map.md`

## Boundary

- no database access
- no external network
- no pipeline execution
- no connector/source/scheduler changes
- no repository documentation mutation by the inspection script
- reports are written only to `exports/doc001_documentation_rebaseline/` when requested
- exports are excluded from the documentation inventory because they are runtime/report artifacts

## Why this comes after GOV-001

GOV-001 established the agent/governance frame. DOC-001A now starts the
documentation rebaseline using that frame.

## Full-ZIP correction

For DOC-001, the full repository ZIP is the correct source of truth. The smaller
handover ZIP is useful for transition context, but it cannot capture the full
documentation and architecture drift surface.

## Inventory command

```bash
python scripts/inspect_documentation_rebaseline.py --write-report --json --label doc001a_full_repo
```

## Classification model

The inventory classifies documentation into buckets such as:

- `current_truth_candidate`
- `reference_candidate`
- `archive_or_historical_candidate`
- `adr_needs_rebaseline`
- `adr_review_candidate`
- `handover_context_not_current_truth`
- `needs_doc001_review`

## Follow-up

DOC-001B should use the generated inventory to define the reduced Current Truth
documentation map and decide which existing docs are promoted, rewritten,
deprecated, or archived.
