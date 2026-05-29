# Employer-Origin Detail Evidence and Incremental Uniqueness Agent

## Status

Proposed for S2T implementation.

## Purpose

S2T extends the employer-origin gate-agent approach beyond the early S2S gates.

The agent reads a DB-backed employer-origin source candidate, fetches a bounded number of detail pages and records:

- `detail_evidence_gate`
- `incremental_uniqueness_gate`

## Boundary

This agent still does not build connector code.

It may:

- read candidate state from PostgreSQL
- reuse preview links from DB-backed gate evidence
- fetch a small bounded set of detail pages
- compare detail candidates against existing raw/Silver evidence
- record gate outcomes in PostgreSQL
- move the candidate to `connector_candidate` only when incremental value is plausible

It must not:

- activate a source
- write Bronze rows
- execute recurring ingestion
- perform broad crawling
- use CSV/Excel/export artifacts as process inputs
- bypass manual review when overlap is unclear

## Why This Matters

This is the first useful step toward an agent that can decide whether building a connector is justified.

The expected employer-origin quantity is low. A candidate may be valuable when one to three relevant jobs appear incrementally unique against current evidence.

## Example

```bash
python -m scripts.run_employer_origin_detail_uniqueness_agent \
  --company-key hdi \
  --target-location hannover \
  --profile-term "product owner" \
  --profile-term data \
  --profile-term sql \
  --max-detail-pages 3 \
  --reviewed-by jens
```

For tricky sources, detail URLs can be supplied explicitly:

```bash
python -m scripts.run_employer_origin_detail_uniqueness_agent \
  --company-key hdi \
  --detail-url "https://example.com/jobs/product-owner" \
  --target-location hannover \
  --profile-term "product owner" \
  --reviewed-by jens
```

## Interpretation

If detail evidence passes and at least one candidate appears incrementally unique, the source candidate can move to `connector_candidate`.

That does not activate the source. It only means the next gate may evaluate whether connector code is justified.
