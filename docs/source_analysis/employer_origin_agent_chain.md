# Employer-Origin Agent Chain Driver

## Status

Implemented as S4A/S4B/S4C candidate workflow driver.

## Purpose

The agent chain driver coordinates the employer-origin agent steps against PostgreSQL gate state.

It does not replace the individual gates. It reads the current DB-backed gate state and runs only the next bounded step:

1. if `detail_evidence_gate` is not passed, optionally run bounded detail-evidence repair
2. if detail evidence is passed but `connector_candidate_gate` is not ready, run the connector-candidate gate agent
3. if `connector_candidate_gate` is passed but full S4A readiness is incomplete, run the connector-build-readiness agent
4. if all required S4A gates and concrete detail evidence are present, run the S4A connector artifact generator
5. by default, artifact generation is dry-run only

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

Write connector files only after the DB-backed connector candidate gate is passed:

```bash
python -m scripts.run_employer_origin_agent_chain \
  --company-key hdi \
  --reviewed-by jens \
  --attempt-repair \
  --write-connector
```

## Interpretation

The chain is the bounded orchestration layer for the S4A/S4B/S4C employer-origin connector-building workflow. It keeps the agent process DB-backed and repeatable while avoiding broad automation leaps.
