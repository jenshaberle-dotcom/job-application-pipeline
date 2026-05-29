# Registration Execution Plan — hdi

## Status

- allowed: `false`
- reason: final approval gate is not passed/approve_connector_registration

## Registration Steps

- Register `hdi:hannover` in ingestion CLI/runner connector mapping.
- Import `src.connectors.hdi` and its connector class.
- Run connector-specific tests and full test suite.
- Run a bounded manual ingestion preview if supported.
- Prepare a separate controlled activation migration/search-profile change.

## Validation

- `python -m compileall src scripts tests`
- `pytest -q`
- `python -m scripts.run_employer_origin_connector_validation_agent --company-key hdi`
- `python -m scripts.run_employer_origin_agent_chain --company-key hdi --reviewed-by jens --plan-only`

## Rollback

- Remove connector mapping from ingestion CLI/runner.
- Revert source-profile activation migration if created in a later activation PR.
- Keep raw_jobs unchanged unless a later controlled activation wrote new rows.

## Forbidden Actions

- Do not enable recurring ingestion in this execution plan.
- Do not write Bronze rows in this execution plan.
- Do not create or enable scheduler changes in this execution plan.
- Do not use CSV/Excel/export artifacts as inputs.

## Boundary

This is an execution plan only. It does not modify connector registration, activation, Bronze persistence or scheduler state.
