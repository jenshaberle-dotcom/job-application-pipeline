# Recurring observation pair projection

Status: LLM-BOOST-001 recurring connector hardening / Issue #537  
Parent authority: Issue #522

## Purpose

Migration 095 persists a truthful evidence hash and evidence-projection contract version on each new `job_observations` sighting. The first real post-095 baseline now exists, but a baseline alone cannot prove `unchanged` or `changed`.

`src/search_intelligence/recurring_observation_delta_projection.py` is the pure deterministic bridge between already-read observation metadata and pair-level delta evidence. It does not query PostgreSQL and does not grant semantic-booster or product authority.

## Exact identity boundary

Observations are paired only inside the exact identity:

```text
source_name + source-local job identity
```

The source-local identity prefers `external_job_id`. Exact `source_url` is used only when no external ID exists. No fuzzy employer, ATS or URL lookalike matching is allowed at this cache/economic boundary.

## Truthful comparison rules

For each exact identity:

1. The first hash-bearing sighting is `baseline_only` / `new`. It is never called unchanged.
2. Two forward-in-time observations with non-null hashes and the same evidence-contract version are comparable.
3. Equal hashes are `unchanged`.
4. Different hashes are `evidence_changed`.
5. A contract-version change is a `contract_boundary`, not content-change evidence. The current sighting becomes the baseline for later observations under the new contract.
6. Historical or unexpected rows without a hash/contract pair are incomparable and break the comparison chain. A later hash-bearing sighting starts a new baseline instead of skipping over the missing evidence.
7. Identity mismatch and non-forward/duplicate timestamps fail closed and are not comparable.
8. Invalid hash/contract pairings are rejected at snapshot construction.

These rules preserve the migration-095 truth boundary: historical evidence is never synthesized or backfilled.

## Aggregate output

`recurring_observation_delta_summary()` reports redacted counts for:

- observation events;
- exact identities;
- classification distribution;
- comparable pairs;
- unchanged pairs and fraction;
- changed pairs and fraction;
- whether an unchanged/changed distribution is available at all.

The projection always reports:

```text
provider_requests = 0
llm_requests = 0
database_writes = 0
product_writes = 0
provider_model_eligible = false
product_authority = false
```

## Separation from booster eligibility

This projection is intentionally narrower than `recurring_connector_economics.py`.

A later runtime read-only audit may use the projection to establish a real post-095 pair distribution. Only after a current observation has also passed the ordinary deterministic connector parse and has an explicit recurring gap family may the existing recurring economics/booster policy consider external stages.

Therefore:

- `unchanged` remains zero-spend and provider/model-ineligible;
- `changed` is evidence of change only, not automatic booster authority;
- a second real sighting is an observational event outside this implementation slice;
- no Daily, provider, LLM, connector activation, lifecycle, ranking, application or product mutation is performed by this contract.
