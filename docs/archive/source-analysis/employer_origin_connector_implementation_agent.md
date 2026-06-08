# Employer-Origin Connector Implementation Agent

## Status

Compatibility wrapper for S4A.

## Purpose

The former implementation-agent entry point remains available for existing local habits, tests and documentation references. The canonical S4A workflow is now:

```bash
python -m scripts.run_employer_origin_connector_artifact_generator --company-key hdi --dry-run
```

The wrapper delegates to `scripts.run_employer_origin_connector_artifact_generator`.

## Boundary

The wrapper does not change the S4A boundary: no connector registration, no source activation, no Bronze persistence, no scheduler changes and no CSV/Excel/export artifacts as pipeline inputs.
