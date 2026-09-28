# JAP execution authority — RCC Warm Pool only

Status: **authoritative**

JAP does not own workload runner allocation.

The only supported execution chain is:

```text
JAP workload demand
→ RCC admission
→ RCC physical-member selection
→ atomic reservation
→ exact repository facade
→ ephemeral assignment label
→ exact-source workload dispatch
→ result verification
→ deterministic cleanup
→ reservation release
```

## JAP authority

JAP may define:

- the workload to execute;
- the exact source SHA;
- the required workload/profile capabilities;
- bounded product inputs and postconditions;
- whether the workload is read-only or has an explicitly approved effect boundary.

JAP must not define:

- a physical runner;
- a fixed repository facade;
- a broad self-hosted routing label;
- a project-owned warm-runner pool;
- heartbeat-based capacity truth;
- a GitHub-hosted fallback for an RCC-managed workload;
- local scheduler or developer-terminal execution as a substitute for RCC admission.

## RCC authority

RCC exclusively owns:

- physical capacity observation;
- member selection;
- reservation and max-active enforcement;
- exact facade lifecycle;
- ephemeral assignment-label creation;
- workload dispatch;
- runner/result identity verification;
- cleanup and reservation release.

JAP declares workload demand in `.rcc/workload-demands.json`; RCC materializes the execution profile. Consumer workflows accept only RCC's exact-source handoff: `source_sha`, `rcc_facade_label` and the ephemeral `rcc_assignment_label`. `runs-on` binds to `self-hosted` plus those two exact RCC labels. The consumer verifies runner/source identity but never infers or chooses pool topology.

## Failure semantics

No suitable capacity means **blocked/waiting**, not fallback.

After an effect-bearing dispatch begins, there is no blind retry. RCC must first establish terminal state or preserve the reservation/facade fail-safe state for recovery.

## Repository boundary

Project-local runner allocation contracts, legacy broad-label workflows, warm-heartbeat routers, direct self-hosted assignments, hosted routing fallbacks and local Windows scheduler wrappers are retired and must remain physically absent.
