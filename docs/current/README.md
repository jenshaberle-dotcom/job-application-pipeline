# JAP current truth

This directory contains current authority only. Historical incidents belong in Git history, not in active sequencing text.

## Product focus

JAP Classic turns verified Employer-Origin vacancies into trusted Product jobs:

```text
Market discovery
→ Employer-Origin verification
→ Bronze
→ Silver
→ Product assessment / Candidate Fit
→ ranking authority
→ Top 5
→ application preparation / tracking
```

For the 1.2.2 product gate:

- Sources must expose the seven current market-discovery sensors through verified evidence;
- at least 10 current Employer-Origin jobs must have evidence-complete Candidate Fit decisions;
- at least 5 must pass the normal Product gates and become rankable;
- authoritative Top 5 must contain exactly 5 jobs;
- Candidate Fit and Affinity remain separate authorities;
- no job/company-specific demo bypass is allowed.

## Execution authority

JAP does **not** allocate runners.

The only supported workload path is:

```text
JAP workload demand → RCC → reserved Warm-Pool member → exact assignment → JAP workload target
```

RCC owns physical selection, reservation, exact facade activation, ephemeral assignment labels, dispatch verification and cleanup.

JAP must not contain project-owned runner pools, broad self-hosted labels, fixed physical-runner selection, heartbeat routing, hosted fallback routing or local scheduler substitutes.

See `ci-max-execution.md`.

## Runtime / desktop

The installed Windows product remains product-local and immutable. Desktop/runtime update authority stays in the product updater code and release assets. Building/publishing the next release must itself be reintroduced as an RCC-assigned workload; the previous repository-owned runner workflow is not authority.

## Re-entry

Read `REENTRY.md` for the exact current engineering gate.
