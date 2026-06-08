# Employer-Origin Registration Execution Plan Agent

## Status

Implemented as S4C registration-readiness planning workflow.

## Purpose

The registration execution plan agent prepares a reviewable connector registration execution plan after final approval.

It does not modify source code or database state beyond writing a human-readable plan when requested. The plan now targets the code-backed connector registry instead of direct CLI control-flow edits.

## Boundary

The plan does not register connectors, activate sources, write Bronze rows, enable recurring ingestion or use CSV/Excel/export artifacts as inputs.

## S4E Registration Target

Connector registration should target `src/connectors/employer_origin_registry.py` through the shared registry foundation. `src/ingest_jobs.py` should remain a CLI/profile orchestration module and should not gain one hardcoded branch per employer-origin connector.
