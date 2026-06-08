# Connector Registration Plan — finanz_informatik

## Status

- readiness: `not_applicable`
- reason: candidate is already active_controlled
- required manual approval token: `approve_connector_registration`

## Candidate

- company: Finanz Informatik GmbH & Co. KG
- source name: `finanz_informatik:hannover`
- source type: `employer_origin_career_site`
- connector class: `FinanzInformatikConnector`
- module path: `src/connectors/finanz_informatik.py`
- test path: `tests/test_finanz_informatik_connector.py`

## Implementation Steps

- Generate or review connector candidate module from DB-backed gate evidence.
- Run connector-specific tests and full test suite.
- Review source scope, request limits and raw_data evidence fields.
- Only after manual approval: register connector in ingestion CLI/runner.
- Only after separate controlled activation: create/enable source target search profile.

## Validation Steps

- `python -m compileall src scripts tests`
- `pytest -q`
- `python -m scripts.run_employer_origin_connector_build_readiness_agent --company-key finanz_informatik`
- `python -m scripts.run_employer_origin_agent_chain --company-key finanz_informatik --reviewed-by jens --plan-only`

## Forbidden Actions

- Do not activate recurring ingestion in this plan.
- Do not write Bronze rows in this plan.
- Do not use CSV/Excel/generated exports as process inputs.
- Do not register the connector without the explicit approval token.
- Do not create a source activation migration in this plan.

## Boundary

This plan is a repository review artifact. It does not register, activate, ingest or schedule anything by itself.
