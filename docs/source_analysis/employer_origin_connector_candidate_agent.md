# Employer-Origin Connector Candidate Agent

## Status

Proposed for S2U implementation.

## Purpose

S2U adds the connector-candidate gate agent.

The agent reads DB-backed employer-origin candidate state and decides whether connector implementation work is justified. It does not generate connector code yet. It records the `connector_candidate_gate` result in PostgreSQL.

## Preconditions

The gate requires these earlier gates to be passed:

1. `company_candidate`
2. `source_discovery`
3. `risk_gate`
4. `technical_reachability_gate`
5. `scope_gate`
6. `defensive_preview_gate`
7. `relevance_gate`
8. `detail_evidence_gate`
9. `incremental_uniqueness_gate`

If any precondition is missing or not passed, the agent records `manual_review_required`.

## What It Produces

The agent records a DB-backed connector-candidate specification as gate evidence.

That specification contains:

- recommended connector module and class names
- source identity and source type
- implementation boundaries
- required raw evidence fields
- detail URLs from the detail-evidence gate
- incremental uniqueness summary
- hard stop conditions for implementation
- minimum tests expected in a connector PR

## Boundary

This gate does not:

- generate connector code
- activate the source
- write raw jobs
- approve recurring ingestion
- use CSV/Excel/export files as inputs

Generated review files are human-readable outputs only. PostgreSQL gate state remains the source of truth.

## Example

```bash
python -m scripts.run_employer_origin_connector_candidate_agent \
  --company-key hdi \
  --reviewed-by jens
```

A successful result means:

```text
connector_candidate_gate: passed / build_connector_candidate
```

It means a connector implementation PR is justified. It does not mean the source is active.
