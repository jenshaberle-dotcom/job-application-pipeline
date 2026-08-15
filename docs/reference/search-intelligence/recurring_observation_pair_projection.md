# Recurring observation pair projection

Status: LLM-BOOST-001 recurring connector hardening / Issues #537 and #540  
Parent authority: Issue #522

## Purpose

Migration 095 persists a truthful evidence hash and evidence-projection contract version on each new `job_observations` sighting. Live acceptance after #537 exposed a second truth boundary: one `src.ingest_jobs` invocation can run multiple profiles/search terms, each with its own `ingestion_runs` row. Those rows belong to one execution and must not be mistaken for later recurrence.

Migration 096 therefore adds nullable `ingestion_runs.execution_id`. Canonical `src.ingest_jobs` creates one opaque UUID per invocation and exposes it through PostgreSQL `application_name`; every ingestion run created by that invocation receives the same execution ID. Historical rows remain NULL. There is no backfill or timestamp inference.

`src/search_intelligence/recurring_observation_delta_projection.py` consumes already-read observation metadata plus the joined execution ID. It does not query PostgreSQL and does not grant semantic-booster or product authority.

## Exact identity and execution boundaries

Observations are grouped inside the exact source-local identity:

```text
source_name + source-local job identity
```

The source-local identity prefers `external_job_id`; exact `source_url` is fallback only. No fuzzy employer, ATS or URL lookalike matching is allowed.

Within one identity, observations are grouped again by exact `execution_id`. The execution is the recurrence boundary, not profile, search term, ingestion-run row or elapsed minutes.

## Truthful comparison rules

1. A row without `execution_id` is incomparable. Historical executions are never inferred.
2. Multiple identical evidence observations inside one execution are duplicate volume only; they do not create recurring pairs.
3. Multiple different hash/contract values for one identity inside one execution are `same_execution_conflict`; that execution cannot be a comparison baseline.
4. The first valid correlated execution is `baseline_only` / `new`.
5. Only a later **distinct** valid execution may be compared with the previous valid execution.
6. Same contract + same hash across distinct executions is `unchanged`.
7. Same contract + different hash across distinct executions is `evidence_changed`.
8. A contract-version change is `contract_boundary`, not content-change evidence; the new execution becomes the later baseline.
9. Missing evidence, identity mismatch, non-forward timestamps or execution re-entry fail closed and break trustworthy comparison state.
10. Invalid hash/contract/execution identifiers are rejected at snapshot construction.

## Why the execution ID is explicit

The first live v1 audit reported 125 apparent pairs from 302 hash-bearing observations, but all 302 observations were produced inside the single 2026-08-15 02:30 Daily window. The old projection was comparing separate profile/search-term ingestion rows inside the same CLI execution. That `81 unchanged / 44 changed` result is not accepted as recurring distribution evidence.

A time-window heuristic would merely hide the same ambiguity. Migration 096 supplies explicit lineage instead.

## Aggregate output

`recurring_observation_delta_summary()` reports redacted execution-level counts including:

- execution events and observation rows accounted;
- exact identities;
- classification distribution;
- same-execution duplicate volume;
- comparable cross-execution pairs;
- unchanged/changed counts and fractions;
- whether a real unchanged/changed distribution exists.

The projection always reports zero DB/provider/LLM/product effects and keeps `provider_model_eligible=false` plus `product_authority=false`.

## Separation from booster eligibility

This projection is narrower than `recurring_connector_economics.py`. A truthful cross-execution `changed` event is still only evidence of change. External provider/model stages additionally require the ordinary deterministic parse/gap eligibility contract and separate authority.

No Daily, provider, LLM, connector activation, lifecycle, ranking, application or product mutation is performed by this projection.
