# S7I Candidate Expansion from Market Observations

## Purpose

S7I bridges the gap between bounded market exploration and modeled employer-origin candidates.

Before this block, the system could run Origin Source Discovery only for companies already present in `employer_origin_source_candidates`. That made the gate portfolio-capable, but the portfolio was still small. S7I reads unregistered company observations from aggregator novelty evidence and creates a reviewable candidate-expansion portfolio.

## Boundary

This block is review and audit state only.

It does not:

- browse external pages
- create employer-origin candidates automatically
- register connectors
- activate sources
- write Bronze records
- change scheduler state
- use CSV/Excel/export artifacts as pipeline inputs

## Input Evidence

Primary input:

- `aggregator_novelty_items`
- `item_type = 'company'`
- `novelty_state = 'unregistered_company'`

Reference input:

- `employer_origin_source_candidates`

The reference input prevents duplicate candidate creation for already modeled companies such as HDI or Finanz Informatik.

## Decisions

Candidate expansion items may produce:

- `create_candidate_recommended`
- `manual_review_required`
- `insufficient_evidence`
- `already_known`
- `active_candidate_monitoring`
- `suppress_as_noise`

## Review Tables

S7I introduces:

- `candidate_expansion_reviews`
- `candidate_expansion_review_items`

These tables are not source-of-truth activation state. They are a durable review layer between market evidence and candidate creation.

## Demo Narrative

The product story becomes:

1. Aggregators reveal market evidence.
2. Novelty logic identifies unregistered companies.
3. Candidate Expansion reviews which companies are worth modeling.
4. Approved/modelled candidates can then enter Origin Source Discovery.
5. Connector build decisions remain gated.

This is the transition from a small candidate set to a broader, controlled market-coverage portfolio.

## Example

```bash
python -m scripts.run_candidate_expansion_from_market_observations_agent \
  --source-name stepstone \
  --reviewed-by jens
```

Persist review state only:

```bash
python -m scripts.run_candidate_expansion_from_market_observations_agent \
  --source-name stepstone \
  --reviewed-by jens \
  --write
```
