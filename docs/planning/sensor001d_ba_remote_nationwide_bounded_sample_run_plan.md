# SENSOR-001D BA Remote/Nationwide Bounded Sample Run Plan

SENSOR-001D creates a bounded sample-run plan for the inactive BA
remote/nationwide review profile. It does not run ingestion.

## Scope

This work item is a planning and guardrail step only.

It may:

- inspect the BA review profile read-only
- create JSON and Markdown plan artifacts under `exports/`
- propose bounded sample terms and measurement criteria

It must not:

- call the BA API
- run ingestion
- write to the database
- activate the review profile
- change the scheduler

## Generic market-sensor requirement

Any market sensor that claims Germany-wide remote-option discovery must have a
bounded sample-run plan before productive activation.

The plan must define:

- maximum sampled terms
- maximum page size / result bound
- required yield and duplicate metrics
- location-distribution review
- remote/hybrid evidence review
- stop conditions
- explicit non-activation boundaries

## Default sample

For the current BA review profile the default sample is intentionally small:

- `Data Engineer`
- `Analytics Engineer`

The profile page size remains bounded to `10`, so the default maximum visible
sample is 20 raw results before later sample-execution logic applies its own
guards.

## Required measurements

A later execution/review work item must measure:

- `total_loaded`, `inserted_count`, and `duplicate_count` per sampled term
- employer uniqueness
- overlap against the local Hannover BA profile
- role/profile relevance
- location distribution
- remote/hybrid signal quality

Volume alone is not source value.

## Follow-up

A later SENSOR-001E may perform the actual bounded sample execution/review after
explicit approval. Productive scheduler activation remains out of scope.
