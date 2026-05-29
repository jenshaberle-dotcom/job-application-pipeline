# Employer-Origin Agent Chain Driver

## Status

Implemented as S2X candidate workflow.

## Purpose

The agent chain driver coordinates the employer-origin agent steps against PostgreSQL gate state.

It does not replace the individual gates. It reads the current DB-backed gate state and runs only the next bounded step:

1. if `detail_evidence_gate` is not passed, optionally run the S2W detail-evidence repair agent
2. if detail evidence is passed but `connector_candidate_gate` is not ready, run the S2U connector-candidate gate agent
3. if `connector_candidate_gate` is passed with `build_connector_candidate`, run the S2V connector implementation agent
4. by default, S2V is run as dry-run only

## Boundary

The chain driver is intentionally conservative.

It does not:

- bypass gates
- infer hidden approval
- write Bronze rows
- activate sources
- enable recurring ingestion
- use CSV/Excel/export artifacts as inputs
- generate connector files unless `--write-connector` is explicitly used and the DB gate state supports it

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

S2X is the first small orchestration layer for the employer-origin connector-building workflow. It keeps the agent process DB-backed and repeatable while avoiding broad automation leaps.
