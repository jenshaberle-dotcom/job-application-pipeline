# Finanz Informatik Legacy Spike Retirement — S2O-A1

## Status

Superseded and retired.

The earlier Finanz Informatik S2J/S2K spike scripts have been removed from the active codebase.

## Reason

The early S2J/S2K workflow was intentionally useful while the source was still unknown:

- it inspected one bounded employer-origin listing page
- it kept network usage small and defensive
- it avoided Bronze persistence
- it helped decide whether a connector candidate was worth building

After S2L, S2M and S2N, the project has a better architecture:

- bounded Finanz Informatik connector-candidate logic lives in `src/connectors/finanz_informatik.py`
- incremental-uniqueness review uses live connector-candidate preview data plus current database evidence
- activation-gate review uses live connector-candidate preview data plus current database evidence
- generated files are review artifacts only

Keeping the old local handoff scripts active would create exactly the kind of architecture debt the project is trying to avoid before cloud migration.

## Current Active Path

Use the current DB-backed / connector-preview-backed path instead:

```bash
python -m scripts.review_finanz_informatik_incremental_uniqueness
python -m scripts.review_finanz_informatik_activation_gate
```

These scripts may write review artifacts under `exports/`, but those artifacts are not pipeline inputs and are not activation-gate inputs.

## Boundary

This retirement does not approve Finanz Informatik Bronze persistence or recurring ingestion.

It only removes the obsolete local handoff path from the active repository.

## Remaining S2O Scope

The remaining larger export-as-input refactor is the historical-burden hot-store removal workflow. That workflow is operationally more sensitive and should be handled in a dedicated DB-backed review-state refactor.
