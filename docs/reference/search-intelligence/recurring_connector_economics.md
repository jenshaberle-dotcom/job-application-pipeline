# LLM-BOOST-001 — Recurring Connector delta and economics boundary

Status: Slice 9 provider-free implementation contract  
Authority: Issue #522

## Purpose

Recurring connector execution is economically different from one-time source discovery. A connector may observe the same source-local job many times. Re-running Tavily or the model cascade for unchanged evidence would create recurring spend without creating new information.

The first recurring slice therefore adds only a pure cache/delta and economics contract. It performs no provider, network, database, lifecycle, ranking, application or product write.

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

The evidence-hash helper deliberately does **not** choose product fields. The caller must supply only durable semantic/structural evidence and exclude volatile transport metadata such as timestamps, request IDs or tracing data. Strings are Unicode-NFC and whitespace normalized; mapping keys are sorted; sequence order is preserved so potentially meaningful source changes are not silently conflated.

## Delta classification

A current evidence record is classified against the cache record for the same connector + source-local job identity:

- `new` — no prior cache record;
- `unchanged` — exact same fingerprint;
- `evidence_changed` — durable evidence changed under the same contract;
- `contract_changed` — booster contract version changed and therefore invalidates the cache;
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

This first contract intentionally chooses economic safety over automatic unchanged retries. A later retry requires a materially changed relevant precondition represented by new evidence or a new contract version; ordinary daily repetition is not such a precondition.

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

The ledger computes observed total cost, cost per validated rescue, request counts, latency and stage-observation distribution. It intentionally does **not** assign a monetary value to a job opportunity, rank candidates or authorize execution. Those are later product/runtime policy decisions and require shadow evidence first.

## Relationship to current recurring ingestion

`src/ingest_jobs.py` already selects only active profiles whose `recurring_ingestion_enabled` flag is true for unscoped/source-family recurring execution. `src/ingestion/runner.py` already preserves source-local duplicate identity through `source_name + external_job_id` and still appends job observations for repeated source sightings.

This slice does not change those ingestion/write semantics. It adds the missing semantic-booster cache/economics contract alongside them so the later integration can decide whether a new observation is worth any external semantic work.

## Promotion sequence

This slice must pass exact-head Pipeline CI and re-entry before any recurring runtime shadow is added.

After merge, the next safe recurring step is a **read-only/provider-disabled shadow classification sample** over real recurring observations. That sample should measure how many cases are `unchanged`, `evidence_changed`, `contract_changed`, deterministically supported, or explicit gap candidates. Only after the delta distribution is proven should a bounded provider/model shadow spend money.

No connector activation, scheduler mutation, ingestion rewrite, lifecycle mutation or default semantic booster activation belongs to this slice.
