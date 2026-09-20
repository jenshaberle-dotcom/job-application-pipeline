# ADR-035: Define Connector Control Plane and Shared Execution Runtime

Status: Accepted for implementation
Date: 2026-09-20

## Context

JAP's employer-origin strategy intentionally prefers controlled employer-origin sources over aggregator truth. As the source estate grows, the product may need hundreds or thousands of employer connectors.

The scalable unit must therefore not be one permanently running service per employer. The existing architecture already provides the important building blocks:

- code-backed connector families and the canonical `generic_origin:<company_key>` product family;
- active `search_profiles` with an explicit `recurring_ingestion_enabled` boundary;
- exact profile execution through `python -m src.ingest_jobs --profile ...`;
- source roles separating `employer_origin` from sensors;
- ingestion-run and observation lineage;
- a private `job-pipeline-runtime` repository that owns secrets-bound execution, scheduler integration, runner routing and exact-SHA runtime evidence.

JAP Cloud also needs continuously refreshed shared catalog data. Reimplementing connectors, product source semantics or runtime authority in the cloud repository would create a second JAP product/runtime truth.

## Decision

JAP uses a **Connector Control Plane + shared worker runtime** model.

A connector is primarily a versioned execution definition, not a dedicated always-on deployment.

The logical topology is:

```text
Connector/source registry + active search profiles
                    |
              shared scheduler
                    |
             connector work item
                    |
          shared stateless worker pool
                    |
             Origin acquisition
                    |
             Bronze -> Silver
                    |
              shared catalog
```

### Connector definition unit

Employer-specific identity remains represented by source/profile configuration such as:

```text
generic_origin:<company_key>
```

Provider-specific and generic acquisition implementations remain reusable capabilities beneath that product family.

An employer may require an exceptional implementation, but the long-term default is:

```text
employer identity/configuration
        +
shared provider/generic acquisition capability
```

rather than a new service deployment.

### Deployment unit

A connector definition is **not** a deployment unit.

Workers are shared by execution class and may execute many connector definitions. Worker classes may diverge when execution requirements genuinely differ, for example:

- deterministic HTTP/API worker;
- browser-capable worker;
- bounded provider/model-assisted diagnostic worker where separately authorized.

There is no architectural requirement for one container, service, VM, GitHub workflow or runner per employer.

### Portable work-item contract

JAP Origin owns the canonical portable connector work-item contract.

The first contract is:

`contracts/connector-work-item-v1.schema.json`

with the implementation helper:

`src/ingestion/connector_work_item.py`

A work item binds at least:

- exact Pipeline source SHA;
- exact active profile identity;
- exact source name and role;
- scheduler slot timestamp;
- deterministic work ID;
- bounded attempt number.

It contains no credentials, fetched job payloads, CV data or user-owned Cloud state.

The deterministic work ID makes a scheduler retry or queue redelivery identifiable without making the acquisition result itself silently idempotent.

### Runtime repository reuse

`jenshaberle-dotcom/job-pipeline-runtime` remains the private operational companion for JAP.

The following runtime concepts are reused directly:

- product/runtime authority separation;
- immutable repository identity;
- exact Pipeline SHA binding;
- private secret boundary;
- explicit effect authority;
- finite timeout/retry policy;
- concurrency control;
- runner capability routing;
- execution/result provenance;
- exact-profile execution.

The current local execution transport is **not** the long-term cloud scheduler transport.

The following mechanisms are local/runtime-specific and must not be copied 1:1 into the cloud data plane:

- Windows Task Scheduler;
- a persistent local WSL checkout as the cloud execution state;
- local PostgreSQL as the cloud catalog store;
- GitHub issue comments as a high-throughput connector queue;
- one monolithic sequential daily process as the scale-out execution model;
- one GitHub Actions workflow invocation per employer as normal recurring operation.

Those remain valid for local JAP and bounded operational/proof paths.

### Cloud adaptation

JAP Cloud consumes the same connector/product contract and acquisition logic through a cloud adapter.

The cloud runtime is expected to replace only transport/infrastructure concerns:

```text
local scheduler        -> cloud scheduler
local invocation       -> queue/work item
warm local runner      -> shared cloud worker pool
PostgreSQL repository  -> Azure shared-catalog persistence adapter
local secrets/env      -> cloud managed identity/secret boundary
```

The connector's meaning, source identity, acquisition evidence and downstream JAP semantics do not change.

JAP Cloud must not fork connector implementations merely because the persistence or worker host differs.

### Persistence boundary

The current `JobIngestionRunner` remains coupled to the PostgreSQL repository surface. Therefore it is **not** declared cloud-portable as a whole.

Cloud reuse is intentionally split:

1. connector/source identity and acquisition code: reusable;
2. work-item contract: reusable;
3. product filtering/evidence semantics: reusable;
4. PostgreSQL persistence adapter: local-specific;
5. Azure SQL/shared-catalog persistence: cloud adapter required;
6. scheduler/queue transport: runtime-specific.

This prevents a false claim that the present local daily runner can simply be moved unchanged into Azure.

## Scaling model

The target scaling unit is queued connector work, not service count.

For example, thousands of registered employer sources may be represented by thousands of small connector/profile definitions while only a bounded number of workers are active concurrently.

The scheduler may use source-specific cadence, backoff and freshness information, but those concerns must remain outside connector product semantics.

## Required invariants

1. One employer connector definition does not imply one always-on service.
2. Product/source semantics remain authoritative in `job-application-pipeline`.
3. `job-pipeline-runtime` remains an operational/runtime authority, not a product authority.
4. Cloud workers consume exact versioned Origin contracts/code.
5. Queue messages contain identifiers and provenance, not secrets or large raw payloads.
6. Connector retries are finite and observable.
7. Source activation remains separate from connector implementation.
8. Browser-heavy work may use a separate worker class without changing the connector identity model.
9. Successful acquisition flows into common Bronze/Silver/shared-catalog semantics.
10. JAP Cloud personal user state remains separate from the shared employer-origin catalog plane.

## Consequences

- Existing connector genericity work remains valuable and becomes the scale mechanism rather than being replaced.
- The Runtime repository is reused substantially, but its local host/scheduler mechanics are not treated as cloud architecture.
- The next cloud implementation step is a shared-catalog connector worker adapter around the portable work-item contract and Origin acquisition code.
- The existing sequential daily runner remains valid for local JAP until a separately proven work-item scheduler supersedes it there.
