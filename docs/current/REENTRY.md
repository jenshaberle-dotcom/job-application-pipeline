# JAP Classic re-entry

Updated for the 1.2.2 runner hard cut.

## Current product target

JAP Classic 1.2.2 is not released yet.

Required product proof before the version bump:

1. all seven market sensors visible in Sources with verified discovery evidence;
2. at least 10 current Employer-Origin jobs with complete Candidate Fit decisions;
3. at least 5 Fit-passed jobs satisfying normal hard-filter/ranking authority;
4. authoritative Top 5 contains exactly 5 jobs;
5. no job IDs, employers, direct rank writes or demo-only promotion bypasses.

The reusable Product target is `.github/workflows/product-v1-assessment-cohort.yml`.

## Runner authority hard cut

The repository no longer owns workload runner allocation.

Canonical chain:

```text
JAP workload demand
→ RCC
→ RCC admission/reservation
→ RCC-selected Warm-Pool member
→ exact repository facade
→ ephemeral assignment label
→ exact-source JAP workload
→ RCC verification/cleanup/release
```

Physically removed from JAP:

- project-owned direct self-hosted assignment workflows;
- broad runtime labels and their freeze/fallback guards;
- heartbeat-based routing;
- fixed Warm-Pool member selection;
- repository-owned hosted/warm route selection;
- retired Blue-runner workflow archive;
- legacy workflow trigger authority files under `.github/triggers/`;
- project-owned runner allocation contract;
- local Windows scheduled-pipeline runner path;
- old workflow-specific regression tests that could restore those authorities.

The remaining assessment-cohort workflow is a **workload target only**. It receives RCC's exact assignment and does not choose pool topology.

## Current next gate

The three residual scans are complete on the residual-proof candidate; see
`docs/current/warm-pool-hardcut-proof.md` for scope, fixes and validation.
The runner hardcut is merged on `main` as `857534c4983398202714c83387af121d1e92115a`;
the Candidate-Fit/Top-5 projection clarification is merged as
`717ae8654c3cff6641fdbcb1567935276cf55608`. This is repository proof, not RCC
live execution acceptance.

The repository hardcut itself may merge once its own scans and regression tests
pass; keeping stale runner authority on `main` is not a valid substitute for an
external runtime acceptance proof. **RCC-dispatched automation** remains separately
gated on a generic RCC handoff that accepts JAP's capability-only demand without
restoring consumer-owned pool/facade allocation authority. The inspected RCC
production adapter still expects the removed consumer allocation contract and a
different dispatch interface. No RCC execution of the JAP assessment workload
has been proven.

JAP Classic may run the same generic assessment cohort locally through the explicit
Control Center operator action `/api/v1/product-v1/assessment-cohort`. That path
selects no runner, creates no scheduler and restores no repository allocation
authority; it delegates only to the existing Candidate Fit, hard-filter and ranking
authorities. Its child report must prove apply mode, exact 10/5/15 targets, zero
provider requests, zero direct rank/Top-5 writes and no combined score before the
Control Center accepts the result.

The cohort acceptance now counts only selected, current Employer-Origin jobs.
Failed Fit decisions count as evaluated, never passed. Duplicate Top-5 identities,
non-contiguous ranks and failed plan authorities fail closed. These are local
regression checks, not evidence that the live database meets the 10-to-5 target.

Product sequence:

1. from the installed/local Classic Control Center, explicitly run **Evaluate current jobs**
   (or the same generic cohort CLI) against exact JAP main;
2. repair reusable evidence blockers while retaining all Fit/hard-filter gates until
   the validated report proves 10 complete Fit decisions, at least 5 Fit-passed/rankable
   jobs and exactly 5 authoritative Top-5 jobs;
3. verify the English Candidate Fit and Top 5 surfaces against that live Product truth;
4. separately reconcile the generic RCC handoff for future automated/remote cohort runs
   and qualify RCC-assigned Windows publication before publishing version 1.2.2;
5. install and run the operator smoke for Sources, All Jobs, Candidate Fit and Top 5.

Do not increment VERSION or claim populated Top 5 until the live assessment report has
`target_met=true`.
