# Connector Registry Foundation

## Status

Implemented as S4E infrastructure.

## Purpose

Connector creation is now routed through a code-backed registry instead of growing `if source_name == ...` branches inside `src/ingest_jobs.py`.

The registry separates three concerns:

1. CLI/profile selection remains in `src/ingest_jobs.py`.
2. Connector instantiation lives in `src/connectors/registry.py`.
3. Employer-origin connector registrations live in `src/connectors/employer_origin_registry.py`.

## Boundary

Registering a connector factory is not source activation.

A registered connector still needs a separately reviewed active search profile / controlled activation migration before ingestion can run and write Bronze rows.

This design keeps S4 registration preparation code-backed and reviewable without CSV/Excel/export-as-input workflows.

## Employer-Origin Fit

Future generated employer-origin connectors can be added to the employer-origin registry extension after final approval. The ingestion CLI does not need a new hardcoded branch for every employer-origin source target.

## Safety Boundary

This foundation does not:

- activate source profiles
- write Bronze rows
- change scheduler behavior
- infer approval from successful validation
- use exports as hidden pipeline inputs
