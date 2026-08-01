# PRD-001 Product Intent Rebaseline

Status: proposed current product gate
Risk: R0 documentation and product decisions only
Owner: Jens

## Goal

Raise the probability that the pipeline becomes the product Jens actually wants by making product behavior explicit, testable and operator-approved before further product-shaping implementation.

## Non-goal

PRD-001 does not redesign the technical pipeline, weaken existing safety gates, call a provider, access the live database, create candidates, activate sources or change scheduler behavior.

## Product authority change

The engineering backlog remains the executable inventory of technical work. It is subordinate to the approved product contract under `docs/reference/product-contract/`.

DON may decide implementation details. DON may not close an open product decision by inference.

## Progressive sequence

### PRD-001A — Confirm current product truths

Review the statements currently recorded in `docs/reference/product-contract/PRD.md` and classify each as:

- approved;
- modified and approved;
- open;
- rejected;
- superseded.

### PRD-001B — Resolve highest-impact product decisions

Resolve only the decisions required for the first useful vertical product slice:

- target profile and adjacent roles;
- geography and working model;
- job truth and freshness;
- Top-5 count/threshold;
- ranking explanation and uncertainty;
- primary review actions;
- minimum V1 journey.

Future decisions may remain open when they do not affect the next slice.

### PRD-001C — Approve representative scenarios

Approve a bounded scenario baseline covering at least:

- strong qualifying jobs;
- fewer-than-target qualifying jobs;
- aggregator without origin evidence;
- employer without active job;
- duplicate job;
- stale/unknown-date job;
- location mismatch;
- semantic role mismatch;
- prior review state;
- uncertainty and ranking tie.

### PRD-001D — Reclassify the critical-path backlog

For each critical-path item, record:

- approved product requirements;
- acceptance scenarios;
- visible operator outcome;
- product/technical/control classification;
- whether product approval is required.

The complete 67-story catalog does not need to be rewritten at once. Start with the active critical path.

### PRD-001E — Select minimal vertical product slice

Choose the smallest slice that lets Jens judge actual product behavior with real or deterministic representative jobs.

The slice should expose filtering, ranking, evidence, uncertainty and review behavior rather than adding another isolated infrastructure layer.

### PRD-001F — Operator acceptance and correction

Jens reviews the visible result and decides:

- accept product behavior;
- correct requirements or scenarios;
- continue evidence gathering;
- reject the proposed behavior.

## Parallel work allowed

The following may continue during PRD-001 when they do not introduce product semantics:

- safety/security fixes;
- defect repairs;
- documentation drift cleanup;
- read-only GENERIC/EXPAND evidence recomputation;
- CI and runtime stabilization;
- wake/runtime infrastructure work under its own gates.

## Product-shaping work gated

The following require the relevant approved PRD decisions and scenarios:

- candidate apply behavior;
- Top-5 semantics;
- ranking and matching product behavior;
- Control Center queue composition;
- operator review actions;
- application intelligence;
- autonomous product decisions.

## Exit criteria

PRD-001 exits when:

1. the first-slice product decisions are approved;
2. representative scenarios are approved;
3. the critical-path items are traceable;
4. a vertical slice has an explicit operator acceptance contract;
5. unresolved decisions remain visibly open rather than silently defaulted.
