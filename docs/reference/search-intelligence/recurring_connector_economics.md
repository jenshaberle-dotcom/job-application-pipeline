# LLM-BOOST-001 — Recurring Connector delta and economics boundary

Status: Slice 10 observation-hash instrumentation contract  
Authority: Issue #522

## Purpose

Recurring connector execution is economically different from one-time source discovery. A connector may observe the same source-local job many times. Re-running Tavily or the model cascade for unchanged evidence would create recurring spend without creating new information.

Slice 9 added the pure cache/delta and economics contract. Slice 10 adds the smallest truthful observation instrumentation needed to classify **future** repeated sightings as unchanged or changed. It does not activate a booster, execute a provider, alter lifecycle truth or backfill historical evidence.

## Canonical cache identity

The semantic cache identity is:

```text
connector_id
+ source-local job identity or exact source URL fallback
+ normalized durable evidence hash
+ LLM-BOOST contract version
```

`src/search_intelligence/recurring_connector_economics.py` reuses the shared `recurring_evidence_fingerprint()` implementation from `llm_booster_policy.py`.

For source-local identity the contract prefers the connector-provided `external_job_id`. This matches the existing ingestion duplicate identity boundary in `JobIngestionRunner` / `JobIngestionRepository`. The exact source URL is used only when the connector has no external job ID.

The generic evidence hash normalizes Unicode/whitespace, mapping-key order and JSON-compatible values conservatively. Sequence order is retained so a potentially meaningful source change is not silently conflated.

## Observation-level evidence projection

Runtime Issue #137 proved that the historical database did not contain enough information to apply that cache identity honestly:

- recurring-enabled profiles: `30` (`12` employer-origin, `18` sensor);
- recurring observation rows: `24,186`;
- source-local identities: `1,470`;
- repeated identities: `909` covering `23,625` observation rows;
- all `24,186` observations already had external source-local IDs;
- `429` repeated identities showed source-URL variation;
- repeated identities with usable `raw_jobs.content_hash`: `0`;
- observation-level hash/payload columns: `0 / 0`.

The read-only Runtime result therefore correctly reported `historical_payload_delta_classifiable=false`. Repeated identity is **not** evidence of unchanged content.

Migration `095_add_recurring_observation_evidence_hash.sql` adds two nullable columns to `job_observations`:

- `normalized_evidence_hash`;
- `evidence_contract_version`.

Historical rows remain `NULL`. The migration performs no inferred backfill because the exact old per-sighting payload no longer exists.

For each future sighting, `src/ingestion/recurring_observation_evidence.py` hashes:

- the exact current `source_url`;
- the connector-provided current raw job/structural evidence after removing top-level execution/query metadata.

Excluded top-level containers are:

- `search_profile`;
- `search_context`;
- `extraction`;
- `matching`;
- `quality_signals`;
- `acquisition_evidence`.

This matters because current connectors legitimately place run-variant data there. For example Personio and StepStone record `observed_at_utc`, while Bundesagentur embeds the search profile/term. Those values must not make the same source evidence look changed merely because another recurring run or search term observed it.

The current evidence projection contract is explicitly versioned as `recurring-observation-evidence.v1`. Hashes are comparable only when both observations have non-null hashes and the same evidence-contract version.

The existing Bronze duplicate identity remains unchanged. `raw_jobs` is not rewritten when a known source-local job is seen again. Instead, the already-append-only `job_observations` sighting stores the **current** hash for that run, including duplicate Bronze sightings.

## Delta classification

A current evidence record is classified against the cache record for the same connector + source-local job identity:

- `new` — no prior comparable cache record;
- `unchanged` — exact same fingerprint;
- `evidence_changed` — durable evidence changed under the same contract;
- `contract_changed` — evidence/booster contract version changed and therefore invalidates the cache;
- `cache_identity_mismatch` — caller supplied a cache record for another connector/job identity; fail closed.

A contract-version change invalidates the cache even when evidence text itself is unchanged.

## Mandatory deterministic-first boundary

New, changed or contract-invalidated evidence is not automatically booster-eligible.

1. Run the ordinary deterministic connector parse/validation first.
2. If deterministic evidence is supported, no external stage is eligible.
3. If deterministic processing has not run, the recurring booster is ineligible.
4. If deterministic processing is unresolved, escalation still requires one explicit recurring gap family:
   - `external_information_gap`;
   - `semantic_ambiguity`;
   - `structural_drift`.
5. An unresolved but unclassified delta fails closed without external escalation.

For `semantic_ambiguity` and `structural_drift`, Tavily is not a routine fetch substitute: the model cascade may be eligible while Tavily remains skipped. Only `external_information_gap` makes Tavily eligible when its independent runtime budget/provider state is `available`.

## Zero duplicate-spend invariant

An `unchanged` fingerprint suppresses **every provider/model stage**, even if the older deterministic result remained unresolved.

This contract intentionally chooses economic safety over automatic unchanged retries. A later retry requires a materially changed relevant precondition represented by new evidence or a new contract version; ordinary daily repetition is not such a precondition.

The decision object itself is side-effect free and reports:

```text
provider_requests = 0
llm_requests = 0
database_requests = 0
product_writes = 0
product_authority = false
```

The shared `llm_booster_policy` plan remains the stage-order authority.

## Opportunity-cost ledger

`RecurringOpportunityCostLedger` is a pure in-memory evidence ledger for later shadow/canary campaigns. It records per fingerprint + booster stage:

- provider/model request counts;
- observed cost;
- latency;
- whether deterministic validation accepted a rescue;
- whether the case progressed;
- delta and gap family.

Duplicate observations for the same fingerprint + stage are suppressed. The ledger refuses any non-zero provider/model spend for `unchanged` evidence.

The ledger computes observed total cost, cost per validated rescue, request counts, latency and stage-observation distribution. It intentionally does **not** assign a monetary value to a job opportunity, rank candidates or authorize execution.

## Promotion sequence

Slice 10 must pass exact-head Pipeline CI and re-entry before the schema/instrumentation can be promoted.

After migration 095 is applied through the normal governed migration path, the first hash-bearing sighting for an identity establishes a baseline only. A later sighting with the same evidence-contract version is required before that identity can be classified `unchanged` or `evidence_changed`.

The next Runtime step is therefore provider-free:

1. verify migration 095 on the live schema;
2. allow ordinary already-authorized recurring ingestion to produce hash-bearing observations;
3. compare only post-instrumentation observation pairs with non-null, same-contract hashes;
4. measure the real `unchanged` / `changed` distribution;
5. only then sample deterministic unresolved changed/new cases for semantic gaps.

Paid provider/model shadow, canary/default activation, connector activation, scheduler mutation, lifecycle mutation, ranking and application mutation remain later gates.
