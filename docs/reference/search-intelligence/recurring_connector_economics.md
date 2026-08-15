# LLM-BOOST-001 — Recurring Connector delta and economics boundary

Status: execution-aware recurring delta + shadow-selection contract  
Authority: Issue #522

## Purpose

Recurring connector execution is economically different from one-time source discovery. A connector may observe the same source-local job many times. Re-running Tavily or the model cascade for unchanged evidence would create recurring spend without creating new information.

The recurring contract therefore separates four concerns:

1. observation instrumentation and lineage;
2. truthful cross-execution delta classification;
3. deterministic-first economics planning;
4. later shadow-sample candidacy.

None of these pure contracts executes a provider/model stage or grants product authority.

## Canonical cache identity

The semantic cache identity is:

```text
connector_id
+ source-local job identity or exact source URL fallback
+ normalized durable evidence hash
+ LLM-BOOST contract version
```

`src/search_intelligence/recurring_connector_economics.py` reuses the shared `recurring_evidence_fingerprint()` implementation from `llm_booster_policy.py`.

For source-local identity the contract prefers the connector-provided `external_job_id`. The exact source URL is used only when the connector has no external job ID. No fuzzy employer, ATS or URL lookalike matching belongs at this cache/economic boundary.

The generic evidence hash normalizes Unicode/whitespace, mapping-key order and JSON-compatible values conservatively. Sequence order is retained so a potentially meaningful source change is not silently conflated.

## Observation-level evidence projection

Runtime Issue #137 originally proved that historical observations did not contain enough per-sighting evidence to classify repeated identity as unchanged content. Migration `095_add_recurring_observation_evidence_hash.sql` therefore added nullable:

- `job_observations.normalized_evidence_hash`;
- `job_observations.evidence_contract_version`.

Historical rows remain `NULL`; there is no inferred hash backfill.

For each later sighting, `src/ingestion/recurring_observation_evidence.py` hashes the exact current source URL plus connector-provided structural evidence after removing run/query metadata containers such as `search_profile`, `search_context`, `extraction`, `matching`, `quality_signals` and `acquisition_evidence`.

The evidence projection is versioned as `recurring-observation-evidence.v1`. Hashes are comparable only when both observations have non-null hashes and the same evidence-contract version.

## Explicit ingestion-execution correlation

The first live pair audit exposed an additional ambiguity: one `src.ingest_jobs` invocation can execute multiple profiles/search terms, each with a separate `ingestion_runs` row. Adjacent observation rows from that single invocation must not be mistaken for later recurrence.

Migration `096_add_ingestion_execution_correlation.sql` adds nullable `ingestion_runs.execution_id`. Canonical `src.ingest_jobs` creates one opaque UUID per invocation and propagates it through PostgreSQL `application_name` (`job-pipeline-ingest:<uuid>`). All profile/search-term ingestion runs inside that invocation therefore share one explicit execution identity.

Historical ingestion runs remain `NULL`. There is no time-window inference, synthesis or execution-ID backfill.

The execution-aware projection in `recurring_observation_delta_projection.py` therefore follows these rules:

1. missing execution correlation is incomparable;
2. repeated identical evidence inside one execution is duplicate volume only;
3. conflicting hash/contract evidence inside one execution fails closed;
4. the first valid correlated execution is baseline only;
5. only a later **distinct** valid execution can be `unchanged` or `evidence_changed`;
6. contract-version changes are comparison boundaries, not content-change evidence;
7. identity mismatch, execution re-entry and non-forward timestamps fail closed.

The projection also carries the exact current normalized evidence hash. This cryptographically binds later economics/shadow selection to the exact current evidence record without exposing raw payload.

## Mandatory deterministic-first economics boundary

A truthful changed pair is still not automatically booster-eligible.

`build_recurring_connector_decision_for_delta()` accepts an already-authoritative recurring delta while preserving the same economics policy as the legacy current/previous cache API.

The gates remain:

1. deterministic connector parse/validation is authority first;
2. `NOT_RUN` is ineligible;
3. `SUPPORTED` is ineligible;
4. `UNRESOLVED` still requires an explicit recurring gap family:
   - `external_information_gap`;
   - `semantic_ambiguity`;
   - `structural_drift`;
5. unresolved + `NONE` fails closed;
6. `UNCHANGED` suppresses every external stage regardless of older unresolved state.

For semantic ambiguity and structural drift, Tavily is not a routine fetch substitute; the model cascade may be planned while search remains skipped. Only an explicit external-information gap makes Tavily eligible when its independent state is `AVAILABLE`.

## Truthful shadow-candidate boundary

`recurring_shadow_selection.py` is the pure join between persisted pair truth and recurring economics.

A projection can be a later shadow-sample candidate only when all of the following are true:

- exact projected identity equals `connector_id + source-local job identity` of the current economics record;
- projected current evidence hash exactly equals the current economics-record hash;
- the projection is a comparable pair from two distinct non-null execution IDs;
- the projection classification and delta are both `EVIDENCE_CHANGED`;
- the current deterministic outcome is `UNRESOLVED`;
- an explicit non-`NONE` recurring gap exists;
- the canonical recurring economics decision is booster-eligible.

`BASELINE_ONLY`, `CONTRACT_BOUNDARY`, missing execution/evidence, same-execution duplicate/conflict, execution re-entry, identity mismatch and non-forward timestamp are shadow-ineligible. `UNCHANGED` may flow into the economics planner only to preserve and prove its zero-spend suppression; it can never become a shadow sample.

The selector itself performs no provider, LLM, network, database or product operation and reports `product_authority=false`.

## Zero duplicate-spend invariant

An unchanged recurring fingerprint suppresses **every provider/model stage**. A later retry requires a materially changed relevant precondition represented by a new truthful cross-execution evidence change or a separately governed contract change; ordinary repetition is not such a precondition.

Pure decisions report zero requests/writes:

```text
provider_requests = 0
llm_requests = 0
database_requests = 0
product_writes = 0
product_authority = false
```

The shared `llm_booster_policy` remains the canonical stage-order authority.

## Opportunity-cost ledger

`RecurringOpportunityCostLedger` remains a pure in-memory evidence ledger for later shadow/canary campaigns. It records per fingerprint + booster stage request counts, observed cost, latency, validated rescue/progression state, delta and gap family.

Duplicate observations for the same fingerprint + stage are suppressed. The ledger rejects non-zero provider/model spend for unchanged evidence. It does not assign monetary value to an opportunity, rank candidates or authorize execution.

## Promotion sequence

Migration 095 and migration 096 are already governed live schema facts. Historical and the first post-095 observations predate execution correlation and intentionally remain incomparable. Current truthful Runtime evidence therefore has no accepted unchanged/changed cross-execution distribution yet.

Provider-free selector plumbing can be implemented and validated now because its contract is purely deterministic and synthetic-testable. That does **not** authorize live shadow sampling.

The live promotion sequence is:

1. allow an ordinary, already-authorized future `src.ingest_jobs` execution to create the first execution-correlated baseline;
2. allow a later distinct ordinary execution to create truthful cross-execution pairs;
3. measure the real unchanged/changed distribution read-only;
4. consider only truthful `EVIDENCE_CHANGED` + deterministic `UNRESOLVED` + explicit-gap cases as shadow candidates;
5. authorize any actual provider/model shadow separately with bounded economics/evidence gates.

Do not force a Daily merely to manufacture continuity evidence. Paid provider/model shadow, canary/default activation, connector activation, scheduler mutation, lifecycle mutation, ranking and application mutation remain separate later gates.
