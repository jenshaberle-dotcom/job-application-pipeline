# Employer-Origin Connector Artifact Generator

## Status

Implemented as S4A connector artifact generation workflow.

## Purpose

S4A turns a passed DB-backed `connector_candidate_gate` into a bounded connector artifact candidate.

The agent reads PostgreSQL gate state and writes reviewed repository files directly:

- `src/connectors/<source_family>.py`
- `tests/test_<source_family>_connector.py`
- `docs/source_analysis/<source_family>_connector_candidate.md`

This is intentionally not an export-as-input workflow. The database gate state is the source of truth, and the generated repository files are normal code review inputs in the branch.

## Boundary

The generated connector candidate still does not:

- register itself in the ingestion CLI
- activate a search profile
- write Bronze rows by itself
- approve recurring ingestion
- use browser automation
- use CSV/Excel/export artifacts as inputs
- persist raw HTML

Activation remains a separate controlled gate.

## Example

```bash
python -m scripts.run_employer_origin_connector_artifact_generator \
  --company-key hdi
```

Use `--dry-run` to inspect planned paths without writing files.

## Interpretation

A successful S4A run means connector artifact work has been materialized into reviewable repository files. It still needs tests, manual review and a separate controlled activation decision.

## Concrete Job-Detail URL Rule

Overview pages, legal pages and career-root pages are not valid detail evidence.

Examples that must not pass as concrete job-detail evidence:

- `/privacy`
- `/datenschutz`
- `/your_career_opportunities`
- `/karriere/jobs`
- `/jobs`
- `/job_board`

A connector-candidate gate may only pass when the detail evidence contains concrete job-detail URLs with specific job-like slugs. If only overview or legal URLs are available, the agent must stop with manual review instead of generating connector code.
