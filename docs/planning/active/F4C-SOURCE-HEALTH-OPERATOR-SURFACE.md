# F4C — Source Health + Operator Surface Consolidation

Status: **ACTIVE / READ-ONLY RECONCILIATION FIRST**

Canonical issue: `#898`

Release target: next available immutable desktop release after exact-head F4C acceptance. Historical fixed version arithmetic is not authority.

## Why this package exists
The installed operator reviews exposed a real observability gap. Current source projections can show a historical ingestion result such as `success` even when the last run is old. That is useful run history, but it is not current Origin/source health.

The same reviews also showed that `Sources`, `Data Layers` and `Operations` overlap in ways that make the operator ask the same question in multiple places without getting a clear answer.

This package is the active frozen Product campaign step after installed F4B acceptance and before F5 application lifecycle work. It does not change ranking, source activation or application authority.

## Current implementation mismatch — repo truth at F4C entry

The first F4C step is evidence, not a UI rewrite.

Current repo truth contains three concrete signals that must be reconciled:

1. historical `source_heartbeat` maps the latest ingestion-run `success` directly to `healthy`;
2. `src/search_intelligence/source_connector_overview.py` similarly maps latest-run `success` to operational `healthy` without explicit cadence/freshness inputs;
3. current `Operations` renders source/connector lifecycle and blocker counts that substantially overlap the `Sources` domain, while `Data Layers` already owns Bronze/Silver/Gold inventory, flow and freshness.

Therefore F4C must first produce a provider-free, mutation-free current-cohort reconciliation before selecting a production health model or changing top-level navigation.

## Operator contracts

### Sources — source/origin control and health
`Sources` owns the answer to:

> Which sources are healthy now, which are overdue/degraded/blocked, and what requires operator attention?

Per-source truth should distinguish at least:

- configured/implemented/validated/approved/registered/active lifecycle state;
- recurring-ingestion eligibility and expected schedule/cadence where one is actually defined;
- last attempted run;
- last successful run;
- last successful persisted observation/evidence time;
- age/overdue state relative to an explicit expected cadence;
- latest run outcome and bounded consecutive-failure signal where available;
- current blocker/attention reason;
- current reachability/validation only when it is actually measured, never inferred from an old success;
- next expected run or explicit `unknown/not scheduled`.

A stale historical `success` must never render as current healthy merely because the old run succeeded.

If no explicit cadence exists, the UI must not invent an overdue threshold. The source-health state must remain `unknown/not scheduled` for that dimension while still showing run age.

### Data Layers — data-flow truth
`Data Layers` owns the answer to:

> Is evidence flowing through Bronze → Silver → Gold, how fresh is each layer, and where is conversion/coverage being lost?

It should focus on layer inventory, recent flow, freshness and conversion/coverage. Source-level health/control belongs to `Sources`. A source-contribution drill-down may remain only where it explains layer flow; it must not duplicate a second competing source-health table.

### Operations — runtime execution truth
`Operations` earns a separate top-level tab only if it answers a distinct question:

> Are the background runtime/scheduler/agent processes executing as expected, and what runtime incident or queue needs action now?

Useful Operations truth includes actual execution/run health, scheduler/worker liveness, stuck/failed work, queues/attention items, last/next execution and actionable incident context. Source-domain health belongs to `Sources`; Bronze/Silver/Gold flow belongs to `Data Layers`.

If JAP cannot yet populate a truthful and actionable runtime-execution read model, `Operations` should be merged/hidden rather than kept as a mostly redundant count dashboard.

## Health model boundary
Current health is not one boolean. The package keeps these concepts separate:

`lifecycle eligibility != scheduler/run history != current reachability != evidence freshness != delivery/product yield`

A source may be valid and active while delivering zero current jobs. A run may succeed while inserting zero rows. A source may have succeeded historically while now being overdue. These must remain distinguishable.

## Phase 1 — read-only reconciliation

Before Product mutation, produce one exact-head artifact across the current source cohort with, where evidence exists:

- source identity + role;
- lifecycle and activation state;
- recurring-ingestion eligibility / scheduling evidence;
- latest run status, start/end timestamps and run age;
- persisted evidence/layer presence separately;
- current operational-health label emitted by Product;
- whether that label is justified by explicit cadence/freshness evidence;
- current reachability measurement availability;
- current blocker/attention reason;
- which operator surface currently presents the same underlying semantic.

The report must quantify at minimum:

- latest-run `success` rows currently projected as `healthy`;
- rows where `healthy` is emitted without explicit cadence/freshness evidence;
- active sources with zero current delivery separately from failed/unhealthy sources;
- source-health semantics duplicated into Data Layers or Operations;
- sources with unknown truth rather than silently coercing them to success.

Boundaries: read-only DB transaction, no provider/network calls, no source/scheduler mutation, no ranking/Top5/application mutation.

## UI consolidation
The package should remove top-level redundancy rather than cosmetically restyle it.

- One canonical source/origin list and attention model under `Sources`.
- `Data Layers` stays flow-centric.
- `Operations` stays only with distinct runtime-execution authority.
- Cross-links/drill-downs are preferred over duplicate tables with slightly different labels.
- Status chips must name the dimension they represent (`last run success`, `overdue`, `source health unknown`, `blocked`, etc.) instead of a context-free `success`.

## Acceptance
F4C is accepted only when a real Product/runtime proof and installed operator test demonstrate:

- intentionally stale/overdue source evidence cannot appear as current healthy;
- current healthy/degraded/stale/unknown semantics are derived from explicit evidence and cadence rules;
- missing cadence remains explicit rather than receiving an invented freshness threshold;
- zero-current-job sources remain distinguishable from unhealthy sources;
- source lifecycle, source health and layer-flow status are not collapsed into one state;
- `Sources`, `Data Layers` and `Operations` each have a non-overlapping operator question, or the redundant surface is removed;
- the operator can identify which source/runtime item needs attention and why without reconciling multiple contradictory tables;
- all projections remain read-only unless an existing separately approved action is invoked;
- no ranking, Top-5, source activation or application authority is introduced;
- exact-head qualification, immutable release/deploy and installed operator acceptance pass.

## Boundaries
- Do not use synthetic heartbeat activity to make a source look healthy.
- Do not treat an old successful ingestion as current Origin reachability.
- Do not make source health depend on producing at least one job.
- Do not invent a cadence for sources that do not have one.
- Do not duplicate RCC runner/fleet responsibility inside JAP.
- RCC/shared-runner performance or lifecycle debt remains non-blocking for JAP unless it prevents an actual JAP acceptance run.

## Sequencing
Current frozen campaign order is:

`F4C -> F5 -> F6`

F5 remains the already-planned Gmail-backed application lifecycle package and is not replaced by this work.
