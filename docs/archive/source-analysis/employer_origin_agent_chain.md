# Employer-Origin Agent Chain Driver

## Status

Implemented as S4A/S4B/S4C candidate workflow driver with post-artifact orchestration.

## Purpose

The agent chain driver coordinates the employer-origin agent steps against PostgreSQL gate state.

It does not replace the individual gates. It reads the current DB-backed gate state and runs only the next bounded step:

1. if `detail_evidence_gate` is not passed, optionally run bounded detail-evidence repair
2. if detail evidence is passed but `connector_candidate_gate` is not ready, run the connector-candidate gate agent
3. if `connector_candidate_gate` is passed but full S4A readiness is incomplete, run the connector-build-readiness agent
4. if all required S4A gates and concrete detail evidence are present but artifact files are missing, run the S4A connector artifact generator
5. if connector artifact files exist but `connector_validation_gate` is not passed, run S4B connector validation
6. if validation is passed, stop until the explicit approval token `approve_connector_registration` is provided
7. after final approval, prepare the non-activating registration execution plan
8. by default, artifact generation is dry-run only

## Boundary

The chain driver is intentionally conservative.

It does not:

- bypass gates
- infer hidden approval
- write Bronze rows
- activate sources
- enable recurring ingestion
- use CSV/Excel/export artifacts as inputs
- generate connector artifact files unless `--write-connector` is explicitly used and the DB gate state supports it
- infer final approval from validation success
- prepare a written registration plan unless `--write-registration-plan` is explicitly used

## Example

Plan only:

```bash
python -m scripts.run_employer_origin_agent_chain \
  --company-key hdi \
  --reviewed-by jens \
  --plan-only
```

Allow bounded repair:

```bash
python -m scripts.run_employer_origin_agent_chain \
  --company-key hdi \
  --target-location hannover \
  --reviewed-by jens \
  --attempt-repair
```

Write connector files only after the DB-backed connector candidate gate and S4A readiness checks pass:

```bash
python -m scripts.run_employer_origin_agent_chain \
  --company-key hdi \
  --reviewed-by jens \
  --attempt-repair \
  --write-connector
```

## Interpretation

The chain is the bounded orchestration layer for the S4A/S4B/S4C employer-origin connector-building workflow. It keeps the agent process DB-backed and repeatable while avoiding broad automation leaps.


## S4D/S4E Continuation Boundary

The chain now uses both DB gate state and repository artifact state. Connector source, test and candidate-documentation files are treated as code artifacts, not as CSV/export pipeline inputs.

After artifact files exist, the next chain step is S4B validation. A passed validation gate does not imply approval. The chain stops with `stop_explicit_approval_required` until the exact approval token `approve_connector_registration` is provided.

Example final approval continuation:

```bash
python -m scripts.run_employer_origin_agent_chain \
  --company-key hdi \
  --reviewed-by jens \
  --approval-token approve_connector_registration
```

Example registration-plan preparation after final approval:

```bash
python -m scripts.run_employer_origin_agent_chain \
  --company-key hdi \
  --reviewed-by jens \
  --write-registration-plan
```

This still does not register a connector, activate a source, write Bronze rows or change scheduler behavior.
