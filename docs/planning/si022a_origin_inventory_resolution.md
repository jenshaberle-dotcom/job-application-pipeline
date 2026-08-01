# SI-022A Origin Inventory Resolution and Dormant Reobservation

Status: implemented review-only foundation  
Risk: R1  
Evidence basis: origin runtime runs `30663046360` and `30685640392`  
Parent capability: `SI-020 Generic Evidence Closure`

## Problem

The deterministic origin grader produced strong positive evidence for E.ON and
correctly retained four ambiguous companies for review. Four successful
`gpt-5.4-mini` calls did not resolve Hannover Rück, msg systems, Materna or x1F.
The remaining uncertainty is not primarily a model-capability problem. It is a
finite combination of:

1. missing relevant-job inventory behind a seed URL;
2. multiple seed URLs that may represent one technical source;
3. multiple non-equivalent sources that may provide different coverage;
4. an expired or temporarily absent triggering job;
5. a live third-party job with no observed official origin;
6. policy boundaries between origin sources and discovery-only sources.

A seed URL must therefore not be selected merely because it is reachable, official
or model-preferred. Every seed URL is observed independently. Source grouping is a
later conclusion based on evidence, not a shortcut around validation.

## Decision

The resolution order is:

```text
external job finding
→ discover bounded seed URLs
→ observe each URL independently
→ extract relevant job inventory
→ establish candidate equivalence where supported
→ select one source family, preserve multiple coverage families, or park
→ reobserve degressively and reactivate on a new external finding
```

The implementation is deterministic and consumes already collected observations.
It performs no URL fetch, provider call, DB access, connector registration, source
activation or scheduler mutation.

## Source roles

| Role | Eligible as origin | Meaning |
|---|---:|---|
| `official_company` | yes | official company-controlled career source |
| `official_ats` | yes | ATS tenant demonstrably bound to the employer |
| `group_official` | yes | official group source with a supported entity scope |
| `third_party` | no | discovery source, aggregator or external job board |
| `unknown` | no | source role not yet proven |

Third-party jobs remain useful evidence. They can reactivate origin discovery and
support a reversible third-party-only hypothesis, but they are not selected as
origin truth.

## Candidate inventory contract

Each seed URL is represented independently by:

- candidate ID and source URL;
- final or canonical URL when observed;
- source role;
- ATS tenant when identified;
- employer or entity scope;
- reachability;
- total observed job count;
- relevant job count;
- stable relevant job keys or IDs.

`relevant_job_count` means jobs that match the target employer/entity and the
bounded relevance criteria. A generic job counter is insufficient.

## Equivalence contract

Two candidates may be grouped into one source family only when their employer
scopes are compatible and at least one explicit equivalence signal exists:

1. same canonical or final URL;
2. same ATS tenant;
3. relevant-job-set overlap at or above `0.80`.

Grouping does not select a source by itself. It establishes that multiple entry
URLs can be served by one connector or one canonical source-family representative.
The deterministic representative preference is:

1. official company URL;
2. official ATS URL;
3. official group URL;
4. unknown URL;
5. third-party URL.

A role preference never overrides missing relevant-job inventory.

## Resolution states

| Observed state | Resolution |
|---|---|
| one origin-eligible source family has relevant jobs | `confirmed_origin` |
| several equivalent URLs form one job-bearing family | `equivalent_source_family` |
| several non-equivalent origin families have relevant jobs | `multi_origin_coverage` |
| relevant jobs exist only on third-party sources | `third_party_discovery_only` |
| high-confidence external job is live, no origin inventory observed | `official_origin_unproven` |
| triggering external job is no longer live, no origin inventory observed | `dormant_origin_candidate` |
| external and origin evidence are both insufficient | `insufficient_evidence` |

### One URL succeeds

When exactly one origin-eligible source family exposes relevant jobs, its canonical
candidate is proposed as the origin representative.

### Both URLs succeed and are equivalent

When both URLs expose relevant jobs and equivalence is proven, they become one
source family. The target connector belongs to the source family rather than to an
arbitrary seed URL. Alternate URLs remain aliases or entry points.

### Both URLs succeed but are not equivalent

When relevant job inventories differ and no equivalence is proven, the result is
`multi_origin_coverage`. Multiple connector candidates are preserved because each
may cover another entity, geography or job subset.

### Both URLs are empty

Technically equivalent empty candidates may still be represented as one dormant
source family. This avoids duplicate reobservation work but does not turn an empty
source into a confirmed connector.

## External-job hypotheses

A currently live external job with confidence below `0.75` does not create an
origin hypothesis. At or above the threshold:

- no official inventory produces `official_origin_unproven`;
- third-party-only relevant inventory produces the reversible hypothesis
  `employer_may_publish_through_third_party_only`.

Hypothesis levels are evidence counters, not probabilities:

| Evidence | Level |
|---|---|
| one live observation or one origin miss | `possible` |
| at least two live observations and two origin misses | `probable` |
| at least three live observations and three origin misses | `strong_but_reversible` |

Any later official job finding invalidates or downgrades the hypothesis.

## Degressive reobservation

An unresolved or dormant source is rechecked after:

```text
1 day → 3 days → 7 days → 14 days → 30 days → event-only
```

After the fifth scheduled retry, routine polling stops. A new external job finding
reactivates observation immediately and resets the attempt counter. Operator
reactivation remains possible.

This plan prevents permanent daily polling of empty sources while remaining robust
to expired seed jobs, seasonal hiring, temporary empty boards, moved ATS paths and
new aggregator findings.

## Baitjob boundary

The implementation must never emit `baitjob = true`. Internal hiring intent cannot
be proven from public listings. A later measurement slice may compute neutral
signals such as:

- repeated reposting with stable content;
- unusually long listing persistence;
- recurring replacement job IDs;
- persistent external visibility without official-origin confirmation;
- cross-source listing inconsistency.

Possible metric names are `persistent_reposting_score` or
`job_listing_persistence_anomaly`. Interpretation remains an operator decision.

## Implementation in this slice

### Domain engine

`src/search_intelligence/origin_inventory_resolution.py` implements:

- immutable candidate and external-signal contracts;
- URL, ATS-tenant and job-overlap equivalence;
- source-family construction;
- all seven finite resolution states;
- degressive and event-driven reobservation planning;
- explicit review-only and no-mutation boundaries.

### Executable runner

`scripts/run_origin_inventory_resolution.py` consumes one JSON payload and writes an
atomic JSON result. It provides a runnable contract for later DB-backed projection
and Daily Runner integration without performing those integrations now.

### Tests

`tests/test_origin_inventory_resolution.py` covers:

- one confirmed origin;
- equivalent job-bearing URLs;
- multiple independent origin families;
- empty equivalent candidates parked as one dormant family;
- the complete `1/3/7/14/30/event-only` schedule;
- immediate reactivation after a new external finding;
- third-party-only and official-origin-unproven hypotheses;
- low-confidence fail-closed behavior;
- employer-scope separation;
- JSON runner output and mutation boundaries;
- explicit prohibition of automated baitjob assertions.

## Acceptance criteria

The slice is complete when:

1. all candidate URLs are evaluated independently in the input contract;
2. grouping requires explicit technical or inventory equivalence;
3. equivalent and non-equivalent multi-URL outcomes remain distinguishable;
4. empty candidates receive a finite reobservation plan;
5. new external findings reactivate observation immediately;
6. third-party sources remain discovery-only;
7. no provider, DB, connector, source or scheduler mutation is possible;
8. targeted tests, full suite and Ruff correctness gate pass in CI.

## Deferred integration

A follow-up `SI-022B` should bind the engine to current DB truth and the Daily Runner:

1. read external seed-job state and candidate observations from approved read models;
2. persist review outcomes and reobservation due dates in dedicated proposal tables;
3. let the Daily Runner select due observations plus event-triggered reactivations;
4. keep connector creation, registration and activation behind existing explicit
   operator gates;
5. add temporal metrics for external-job persistence and origin misses.

This separation is intentional. The current slice proves the state machine before
introducing migrations, scheduler behavior or write paths.
