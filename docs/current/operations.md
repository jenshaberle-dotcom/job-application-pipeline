# Operations Current Truth

Status: current truth  
Active product track: **PRODUCT-RECOVERY-001 / issue #783**

Operational work is CLI-first, repository-backed and deliberately explicit. The goal is reliable product truth with minimal operator repair, not clever terminal choreography.

## Canonical workspace

Repository-owned workspace policy is authoritative through `PROJECT-LOCAL-WORKSPACE.json` and project hygiene contracts.

Current operator convention:

- persistent canonical checkout: `$HOME/projects/job-application-pipeline` on clean `main`;
- feature worktrees: `$HOME/worktrees/job-application-pipeline/<feature>`;
- feature worktrees must start from fresh remote `main`;
- project feature worktrees must not be created under `/tmp`;
- runner workspaces are execution-only and are not project worktrees.

Before mutation, freshly confirm repository identity, origin, branch, HEAD, upstream and worktree cleanliness.

## Current operator entry points

- `../guides/development-workflow.md` — branch/worktree, commit, PR, merge and cleanup.
- `../guides/operator-runbook.md` — local operation and recovery.
- `../guides/testing.md` — test expectations.
- `scripts/run_validate001_unified_validation.py` — unified repository validation.
- `../reference/operations/db_migration_tracking.md` — migration tracking.
- `.github/RELEASE_MANAGEMENT.md` — release/version/release-note process.

## DEMO-001 retained operator tools

The following tools are retained as product/recovery evidence from the salvaged demo path:

- `scripts/run_demo_001_local_server.py` — robust local Product V1 server start with readiness wait;
- `scripts/run_demo_001_operator_smoke.py` — bounded end-to-end operator smoke;
- `scripts/run_demo_001_rankable_refill_scout.py` — live read-only refill candidate scout;
- `scripts/run_demo_001_rankable_refill_integrity.py` — detail/assessment integrity preflight;
- `scripts/run_demo_001_rankable_refill_campaign.py` — bounded assessment-refresh/refill recovery campaign;
- `scripts/run_demo_001_hard_filter_evidence_close.py` — evidence-bound hard-filter closure for the demo cohort;
- `scripts/run_product_v1_top5_policy_review.py` — explicit recommendation-policy review helper.

These scripts are **not the desired steady-state product workflow**. PRODUCT-RECOVERY-001 must reduce the need for them by producing one normal cold-to-application orchestration path. Retain them until their evidence/recovery value is harvested and replacement coverage exists.

## Local runtime truth

GitHub CI cannot prove local runtime state.

Local-only facts include:

- PostgreSQL contents and current schema application state;
- live employer HTTP/current-vacancy state;
- private Candidate Facts/base CV/base letter files;
- local OpenAI/provider credentials and provider behavior;
- scheduler/process state;
- files generated on the operator workstation.

A merged PR or green CI must never be described as proof of these runtime facts.

## Local Product V1 demo/recovery server

The canonical demo/recovery helper is `scripts/run_demo_001_local_server.py` rather than fixed sleeps around the server process.

The launcher must:

- load the canonical local `.env` without printing secrets;
- use the approved local private-document root;
- run from the intended repository/worktree;
- wait for actual HTTP readiness;
- fail with useful logs if the process exits before ready.

Fixed `sleep 3` style checks are not reliable startup proof and were retired after DEMO-001 startup races.

## Application preparation runtime

Application generation requires approved private source documents and Candidate Facts.

Current local document toolchain includes Python DOCX/PDF support and produces:

- CV `.docx`;
- CV `.pdf`;
- application letter `.docx`;
- application letter `.pdf`;
- ZIP package containing the four files plus manifest/checksum metadata.

Provider behavior:

- only the explicit Generate action may trigger application drafting;
- approved base-document text may be sent to the configured provider as structure/style context;
- Candidate Facts and exact vacancy evidence remain factual authority;
- provider failure may fall back to evidence-first drafting;
- output remains `draft_for_review`;
- no submission/send action is performed.

## Product Recovery operating target

The target operational experience is one command/operator action that can be observed stage by stage:

```text
market discovery
-> Employer-Origin resolution
-> live currentness
-> Bronze / Silver
-> assessment / capability / hard filters
-> ranking / recommendation
-> Application Workspace
-> review-ready document package
```

Normal operation should not require the operator to manually invoke separate integrity, refill, evidence-close and policy-repair scripts between these stages.

## Current acceptance metric

The key runtime proof is not merely `RANKABLE >= 5`.

The approved product contract requires:

- current Employer-Origin truth;
- complete required evidence;
- no hard-filter blocker;
- authoritative rankability;
- recommendation score >=70 for Top-5 eligibility;
- at most five recommendations;
- application generation that is technically valid **and** visually/content-wise close to submission quality.

A truthful result may contain fewer than five recommendations when the market/pipeline does not produce five jobs above the approved threshold.

## Release operations

Product-facing history is published through GitHub Releases rather than reconstructed from commits.

Preferred flow:

```text
feature PR
-> merge to main
-> release notes / release request PR
-> exact-SHA Pipeline CI + Re-entry Identity
-> GitHub Release
```

Versioned release requests live under `.github/release-requests/`. Visibility promotions for an existing pre-release live under `.github/release-promotions/`. Tags are immutable.

Release notes must distinguish:

- repository-shipped behavior;
- local operator proof;
- known limitations;
- product/safety boundaries.

## Failure and retry governance

There is no global fixed attempt-count ceiling.

Retries are evidence-driven:

- preserve the exact failure family/evidence;
- do not repeat an unchanged action against unchanged failure conditions merely to increase an attempt count;
- retry after a relevant precondition changes, infrastructure incident resolves, or the implementation/diagnostic approach materially changes;
- stop or change approach when evidence demonstrates the current approach is exhausted or unsafe.

Attempt counts are diagnostic history, not authority by themselves.

## Repository-backed re-entry contract

Re-entry restores continuation context from durable repository/runtime evidence. It is not a chat handover.

### Target identity

Before a freeze record, PR, runtime observation or next action can establish continuation authority:

- authenticate immutable repository identity using `docs/current/REPOSITORY-IDENTITY.json`;
- Pipeline execution target is GitHub repository ID `1230805345`;
- related repositories may provide evidence/runtime support but are not mutation authority for this repo.

### Re-entry sequence

1. Read `PROJECT-REENTRY.json` and this current-truth surface from canonical `main`.
2. Authenticate current repo/main/workspace identity.
3. Read the active product track: PRODUCT-RECOVERY-001 / issue #783.
4. Compare live repository/PR/CI/runtime truth against any retained checkpoint.
5. Preserve completed evidence only when it belongs to unchanged identity/head/runtime conditions.
6. Inspect database/live evidence before product-side continuation; never replay side effects just to recreate a prior narrative.
7. Resume from the newest legal durable state.

A re-entry record may identify a next safe action but never loosens Product, evidence or side-effect gates.

## Post-merge verification

After every product-significant merge:

- resolve exact new `main` SHA;
- verify required push CI/re-entry jobs for that SHA;
- reconcile current docs/re-entry when sequencing changed;
- create/update the appropriate release checkpoint when product-visible behavior changed;
- separately perform local operator proof when release claims depend on local DB/live/provider behavior.
