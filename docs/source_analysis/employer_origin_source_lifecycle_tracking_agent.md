# Employer-Origin Source Lifecycle Tracking Agent

## Status

Implemented as S2Y candidate workflow.

## Purpose

The source lifecycle tracking agent closes the last employer-origin gate for controlled sources.

It reads PostgreSQL evidence for a candidate source and records the `source_lifecycle_tracking` gate from current DB state. This keeps source lifecycle decisions DB-backed instead of relying on manual notes or exported review files.

## Inputs

The agent reads:

- `employer_origin_source_candidates`
- `raw_jobs`
- `silver_jobs`
- `ingestion_runs`
- `employer_origin_candidate_gate_reviews`

## Boundary

The lifecycle tracking agent does not:

- activate a source
- deactivate a source
- write Bronze rows
- transform Silver rows
- enable recurring ingestion
- use CSV/Excel/export artifacts as inputs

It only records the lifecycle gate in PostgreSQL.

## Decision Logic

- raw evidence and Silver evidence exist: `passed / continue`
- raw evidence exists but no Silver value exists: `manual_review_required`
- no raw evidence exists: `manual_review_required`

## Example

```bash
python -m scripts.run_employer_origin_source_lifecycle_tracking_agent \
  --company-key finanz_informatik \
  --reviewed-by jens
```

## Interpretation

S2Y makes the employer-origin gate model complete for active controlled sources. It does not replace longer-term source-value KPIs, but it prevents `source_lifecycle_tracking` from remaining indefinitely `not_started` after a source is already active.
