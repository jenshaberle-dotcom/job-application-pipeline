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

Finish the three hard-cut deep scans and merge only when the residual scan proves that the JAP execution surface contains no old runner authority.

After that:

1. complete/use the generic RCC production handoff;
2. run the 10→5 Product flight on exact JAP main;
3. repair only reusable Product/evidence blockers;
4. set VERSION to 1.2.2;
5. rebuild release publication as an RCC-assigned Windows workload;
6. install and run the operator smoke for Sources, All Jobs, Candidate Fit and Top 5.
