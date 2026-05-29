# Employer-Origin S4 Post-Artifact Orchestration

## Status

Implemented.

## Purpose

This note documents the S4D/S4E continuation after S4A connector artifact generation.

The workflow now supports a bounded progression from DB-backed gates to repository artifacts and then back to DB-backed validation/approval state:

1. S4A generates connector candidate artifacts only after the required gates and concrete job-detail evidence are present.
2. S4B validates existing connector artifacts through compile/import/test/safe-preview evidence.
3. S4C final approval requires the exact token `approve_connector_registration`.
4. Registration planning remains non-activating and does not alter runner, scheduler or Bronze persistence behavior.

## Architecture Boundary

Repository files are code artifacts. They are not CSV/Excel/export handoffs and are not data-pipeline inputs. The chain may inspect whether the expected code artifacts exist, but it must not use generated human-review exports as hidden source-of-truth inputs.

## Safety Boundary

This orchestration does not:

- register connectors in the ingestion runner
- activate source profiles
- write Bronze rows
- change scheduler behavior
- infer final approval from successful validation
- use CSV/Excel/export artifacts as pipeline inputs

## Human Approval Boundary

A passed `connector_validation_gate` only means the connector candidate is ready for human final approval. Registration planning remains blocked until `final_approval_gate` is passed with decision `approve_connector_registration`.

The candidate queue intentionally has no approval-token path. It can surface the stop condition, but it cannot approve.
