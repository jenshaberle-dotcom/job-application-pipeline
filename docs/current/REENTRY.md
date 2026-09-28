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
- project-owned runner allocation contract;
- local Windows scheduled-pipeline runner path;
- old workflow-specific regression tests that could restore those authorities.

The remaining assessment-cohort workflow is a **workload target only**. It receives RCC's exact assignment and does not choose pool topology.

## Current next gate

The three residual scans are complete on the residual-proof candidate; see
`docs/current/warm-pool-hardcut-proof.md` for scope, fixes and validation.
Main changes through `c0e3002db601289592eddd28ef96225ddc992476` are integrated.
This is local repository proof, not RCC live execution acceptance.

Before merge/product execution, qualify a generic RCC handoff that accepts this
repository's capability-only profile and exact assignment input contract.
The inspected RCC main dispatcher still requires the removed consumer allocation
contract. The inspected RCC hardcut dispatcher ends at its pre-dispatch boundary.
Neither observation proves execution of the JAP assessment workload.

Product sequence after that gate:

1. run the reusable 10→5 assessment workload on exact JAP main;
2. repair reusable evidence blockers while retaining all Fit/hard-filter gates;
3. verify the existing English Candidate Fit and Top 5 surfaces against live data;
4. qualify RCC-assigned Windows publication before publishing version 1.2.2;
5. install and run the operator smoke for Sources, All Jobs, Candidate Fit and Top 5.

Do not increment VERSION or claim populated Top 5 from static/local tests.
