# Employer-Origin Gate Agent MVP

## Status

Proposed for S2S implementation.

## Purpose

S2S introduces a first bounded gate-agent MVP for employer-origin source candidates.

The agent does not build connector code. It executes the first gates of the S2Q process and records the result in the S2R DB-backed gate-state model.

## Boundary

The gate agent is intentionally limited.

It may:

- create or update an employer-origin source candidate
- initialize the standard gate list
- execute early gates up to relevance
- perform one bounded read-only request
- record gate outcomes in PostgreSQL
- stop with a documented reason

It must not:

- write raw jobs
- activate a source
- generate connector code
- perform broad crawling
- use CSV or Excel as input
- use generated exports as process state
- bypass failed hard gates

## MVP Gates

The first implementation covers:

1. `company_candidate`
2. `source_discovery`
3. `risk_gate`
4. `technical_reachability_gate`
5. `scope_gate`
6. `defensive_preview_gate`
7. `relevance_gate`

Later stages can extend this to:

- detail evidence
- incremental uniqueness
- connector-candidate generation
- controlled activation support

## Example Run

```bash
python -m scripts.run_employer_origin_gate_agent \
  --company-key hdi \
  --company-name "HDI Group" \
  --candidate-url "https://careers.hdi.group/en/your_career_opportunities/job_board" \
  --source-name-candidate "hdi:hannover" \
  --source-family-candidate hdi \
  --source-target-candidate hannover \
  --target-location hannover \
  --profile-term "product owner" \
  --profile-term data \
  --profile-term sql \
  --reviewed-by jens
```

## Interpretation

A stopped run is not a failed project result.

A stopped run means the source candidate did not satisfy the current gates. The stop reason is preserved in the database and can support a later manual review, a documented abort or a different candidate strategy.

## Next Step

After this MVP proves useful, the next step is a detail-evidence and incremental-uniqueness gate runner. Connector code generation should remain blocked until those gates pass.
