# F4C — Source Health + Operator Surface Consolidation

Status: FROZEN / QUEUED AFTER F4B

Target desktop release: `1.0.28`

## Why this package exists
The installed v1.0.25 operator review exposed a real observability gap. Current source projections can show a historical ingestion result such as `success` even when the last run is old. That is useful run history, but it is not current Origin/source health.

The same review also showed that `Sources`, `Data Layers` and `Operations` currently overlap in ways that make the operator ask the same question in multiple places without getting a clear answer.

This package is added to the frozen Product campaign without changing Product authority. It is intentionally placed after F4B ranking and before F5 application lifecycle work: F4A/F4B decision intelligence remains the immediate critical path, while the operator observability debt gets a named, non-droppable package before the workflow expands into Gmail-backed application tracking.

## Operator contracts

### Sources — source/origin control and health
`Sources` owns the answer to:

> Which sources are healthy now, which are overdue/degraded/blocked, and what requires operator attention?

Per-source truth should distinguish at least:

- configured/implemented/validated/approved/registered/active lifecycle state;
- expected schedule/cadence where one exists;
- last attempted run;
- last successful run;
- last successful persisted observation/evidence time;
- age/overdue state relative to the expected cadence;
- latest run outcome and bounded consecutive-failure signal where available;
- current blocker/attention reason;
- current reachability/validation only when it is actually measured, never inferred from an old success;
- next expected run or explicit `unknown/not scheduled`.

A stale historical `success` must never render as current healthy merely because the old run succeeded.

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
Current health is not one boolean. The package should keep these concepts separate:

`lifecycle eligibility != scheduler/run history != current reachability != evidence freshness != delivery/product yield`

A source may be valid and active while delivering zero current jobs. A run may succeed while inserting zero rows. A source may have succeeded historically while now being overdue. These must remain distinguishable.

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
- Do not duplicate RCC runner/fleet responsibility inside JAP.
- RCC/shared-runner performance or lifecycle debt remains non-blocking for JAP unless it prevents an actual JAP acceptance run.

## Sequencing
Frozen campaign order after the v1.0.25 operator review:

`F4A-Q / 1.0.26 -> F4B / 1.0.27 -> F4C / 1.0.28 -> F5 / 1.0.29 -> F6 / 1.0.30`

F5 remains the already-planned Gmail-backed application lifecycle package and is not replaced by this work.
