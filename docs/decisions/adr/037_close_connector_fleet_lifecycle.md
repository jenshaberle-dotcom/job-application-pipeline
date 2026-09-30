# ADR-037: Close the Connector Fleet Lifecycle

Status: Accepted by operator direction
Date: 2026-09-30
Canonical issue: #1150

## Context

JAP already separates weak market-sensor evidence, Employer-Origin candidates, connector
validation, registration, activation and ingestion. That separation is correct, but it leaves
an operational blind spot when a candidate is discovered without becoming a durable recurring
observation unit.

A company that mattered once must not silently fall out of observation. The product therefore
needs a closed lifecycle from discovery into recurring connector monitoring, with one shared
health contract for Classic and Cloud.

Existing architecture already provides the pieces:

- Employer-Origin candidate and gate lifecycle;
- reusable generic/ATS-family connector capabilities;
- active search profiles and `recurring_ingestion_enabled`;
- portable connector work items;
- exact-profile execution and ingestion lineage;
- Classic Runtime/RCC execution authority;
- Cloud shared-worker topology;
- read-only source-health and recent-yield evidence.

The missing authority is the fleet-level invariant that joins them.

## Decision

JAP adopts a **closed connector-fleet lifecycle**.

```text
Market Sensor
  -> Employer Candidate
  -> Origin / Detail Evidence
  -> Connector Work Definition
  -> Validation
  -> Registration
  -> Bounded First Execution
  -> Recurring Monitoring Admission
  -> Due-Work Scheduling
  -> Connector Execution
  -> Persisted Run + Yield Evidence
  -> Connector Fleet Status
  -> next due execution
```

Every accepted Employer-Origin candidate must receive an explicit connector disposition.
It may become runnable, blocked with evidence, require manual review, or be rejected with
evidence. It may not remain silently outside the connector lifecycle.

"Build a connector" means materialize a runnable connector/profile definition. It does not
mean one bespoke Python implementation or one service deployment per employer. Shared
generic and ATS-family capabilities remain the default.

## Canonical policy

The machine-readable authority is:

`config/connector_fleet_policy.json`

Initial defaults:

- recurring cadence: **24 hours**;
- recent relevant-yield window: **7 days**;
- overdue grace: **6 hours** beyond the expected cadence;
- deterministic slotting across the cadence window from source/profile identity;
- global concurrency cap: **5**;
- default provider/host concurrency cap: **2**;
- finite retries: 3 attempts with bounded backoff.

These are product defaults, not UI assumptions. They may later be changed through the
canonical policy without creating separate Classic/Cloud semantics.

## Scheduling

The scheduler must not launch the whole fleet at one wall-clock time.

Each recurring-admitted source/profile gets a stable deterministic slot within its cadence
window. A stable hash is preferred over alphabetic batching because it is reproducible while
distributing unrelated employer/provider identities more evenly.

Execution transport is separate from scheduling semantics:

- Classic Runtime derives due work and executes it only through RCC-owned execution admission;
- Cloud adapts the same due-work semantics to its approved queue/shared-worker transport;
- neither transport owns a second cadence or health definition.

## Health and traffic light

Technical health and job yield remain separate evidence dimensions. The Control Center may
derive one operator traffic light only from both dimensions:

### GREEN

- connector/profile is technically current and recurring-admitted; and
- at least one authoritative relevant current job attributable to this source/search profile
  was observed within the last 7 days.

### YELLOW

- connector/profile is technically current and recurring-admitted; and
- no authoritative relevant current job was observed within the last 7 days.

Zero yield is therefore not a technical failure.

### RED

Any current technical/runtime failure, including:

- latest due execution failed;
- source/profile is overdue beyond cadence plus grace;
- registration/validation is broken;
- execution is blocked.

Older jobs must not keep a technically broken connector green.

### Neutral lifecycle state

Candidates still in build/validation/approval/registration are not operational connectors yet
and must remain a neutral lifecycle state rather than receiving a misleading traffic light.

The UI must expose the evidence behind the light: last attempt, last success, next due,
recent relevant-yield count/time, consecutive failures and current blocker.

## Yield authority

Raw `total_loaded > 0` is not sufficient to make a connector green.

The green signal must come from authoritative current Product job truth attributable to the
source and configured search/profile boundary. The implementation may evolve, but it may not
substitute raw page/result count for job relevance.

## Repository responsibilities

### job-application-pipeline

Owns:

- connector/source identity;
- candidate-to-connector lifecycle semantics;
- fleet policy;
- health/yield/traffic-light semantics;
- portable DTO/contracts consumed by the Control Center and Cloud.

### job-pipeline-runtime

Owns Classic/private execution only:

- due-work materialization from the Origin policy;
- exact Pipeline/profile/source binding;
- RCC admission;
- bounded concurrency/retry;
- durable execution evidence.

Runtime does not own product health semantics.

### jap-cloud-based

Owns Cloud adaptation only:

- queue/worker transport;
- cloud persistence adapter;
- cloud execution/scaling observability;
- API projection of the same Origin-owned contract.

Cloud must not fork connector-fleet semantics.

## Required invariants

1. Accepted candidate -> explicit connector disposition is mandatory.
2. Active-controlled source -> recurring-monitoring disposition is mandatory.
3. Connector definition != dedicated deployment.
4. Technical health != job yield.
5. Zero recent jobs while execution is healthy -> YELLOW, not RED.
6. Technical failure/overdue -> RED even when historical jobs exist.
7. Recovery is determined from current execution + current yield evidence.
8. Classic and Cloud consume the same policy and UI semantics.
9. Scheduling is deterministic, staggered and bounded.
10. No connector run may be silently skipped without observable due/run evidence.

## Implementation links

- Product/Classic: #1150
- Classic Runtime: jenshaberle-dotcom/job-pipeline-runtime#398
- Cloud adaptation: jenshaberle-dotcom/jap-cloud-based#115
- Existing Runtime inventory: jenshaberle-dotcom/job-pipeline-runtime#203
- Existing source-health work: historical #898
