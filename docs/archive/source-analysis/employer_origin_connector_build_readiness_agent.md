# Employer-Origin Connector Build Readiness Agent

## Status

Implemented as S3B candidate workflow.

## Purpose

The connector build readiness agent evaluates whether an employer-origin source candidate may generate connector implementation files before final approval.

It reads PostgreSQL-backed candidate and gate state and checks:

- all required discovery, risk, reachability, scope, relevance, detail, uniqueness and connector-candidate gates are passed
- `connector_candidate_gate` decided `build_connector_candidate`
- connector-candidate spec exists
- concrete detail URLs exist
- no non-deferred manual-review or blocked gates are open

## Boundary

The readiness agent does not:

- generate connector code
- register connectors
- activate sources
- write Bronze rows
- enable recurring ingestion
- use CSV/Excel/export artifacts as inputs

It only reports whether connector generation is allowed before final approval.
