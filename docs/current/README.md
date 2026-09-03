# Current Truth

Status: current truth navigation  
Active product track: **PRODUCT-RECOVERY-001 / issue #783**  
Current release checkpoint: **`v0.1.0-demo.1`**

This folder is the maintained current-truth surface. It is intentionally not a complete project history.

## Re-entry authority

Every re-entry starts from canonical `refs/heads/main` and `PROJECT-REENTRY.json`, then reads this current-truth surface.

A branch-local copy, old checkout, historical planning file, release note, issue comment or familiar worktree may contain useful evidence but cannot redefine canonical `main` or active sequencing by itself.

Repository-owned workspace/hygiene/retention contracts remain authoritative:

- `PROJECT-HYGIENE.json`;
- `PROJECT-LOCAL-WORKSPACE.json`;
- `PROJECT-DRJ.json`;
- `POST-MIGRATION-RESTART.json`.

## Current project state

### DEMO-001 — salvaged checkpoint

DEMO-001 / #707 is retained as a proven product checkpoint, not current long-term sequencing authority.

- salvage PR: `#781`;
- salvage merge: `d63ba7125693b19286d93b8d32bd955581ac84cd`;
- release checkpoint: `v0.1.0-demo.1`;
- retained planning/evidence anchor: `../planning/active/demo_001_live_e2e_reentry.md`.

The checkpoint established working capabilities across:

```text
discovery -> Employer Origin -> current detail
-> Bronze / Silver -> Product V1 assessment/ranking
-> React Control Center -> Application Workspace
-> CV/letter DOCX/PDF/ZIP draft_for_review
```

It also exposed integration debt. The existence of the checkpoint does not mean the cold product flow is production-ready.

### PRODUCT-RECOVERY-001 — active continuation

Issue **#783** is the current product priority.

Canonical active plan:

- `../planning/active/product_recovery_001.md`.

Primary product truth:

```text
market discovery
-> Employer-Origin resolution
-> freshly verified exact vacancy
-> Bronze / Silver
-> assessment
-> capability fit
-> hard filters
-> deterministic ranking
-> recommendations meeting the approved Product contract
-> Application Workspace
-> near-submission-quality review package
```

Primary acceptance target:

> **At least five current Employer-Origin jobs meeting all approved evidence/hard-filter gates and the current 70/100 recommendation threshold, produced through one normal observable flow; plus an application package requiring only small human edits.**

`rankable >= 5` by itself is not success. `PD-050/PD-051` remain authoritative: Top 5 is at most five and is not filled with jobs below the approved quality threshold.

### ACQ-GENERALIZATION-90 — preserved

Issue #676 remains retained and resumable, but is not current sequencing authority.

Retained anchors:

- `../planning/active/acq_generalization_90_reentry.md`;
- `../planning/active/acq_generalization_90_reentry.json`;
- `../planning/active/acq_generalization_90_target.md`;
- `../planning/active/acq676_external_deterministic_salvage.md`.

Reuse generic deterministic capabilities when they directly advance Product Recovery; otherwise leave the track paused until explicit reprioritization.

## Current product truth summary

The project is now a Search Intelligence **and application-preparation** product, not only a discovery/connector system.

Important current boundaries:

- BA/StepStone/GuteJobs and similar aggregators discover; Employer-Origin confirms Product/Application action authority.
- Historical observation does not prove current vacancy state.
- Detail drift invalidates stale assessment/ranking evidence and requires audited refresh.
- `rankable` and `recommended` are distinct states.
- Top-5 current minimum overall quality is 70/100.
- Candidate Facts remain candidate factual authority; exact current vacancy evidence remains job factual authority.
- Application provider calls occur only through explicit Generate behavior approved by the product contract.
- Application output remains `draft_for_review`; no auto-submit/send exists.
- CI does not prove local PostgreSQL/provider/live employer state.

## Release management

GitHub Releases are the product-facing change history.

Canonical release surfaces:

- `.github/RELEASE_MANAGEMENT.md`;
- `.github/release.yml`;
- `.github/workflows/release.yml`;
- `.github/release-notes/`;
- `.github/release-requests/`;
- `.github/release-promotions/`.

Release notes explain features, bug fixes, known limitations and relevant operator proof. Commit history remains engineering detail.

Tags are immutable. GitHub release visibility may be promoted without changing version/tag target or implying production readiness.

## Local operator proof vs repository truth

DEMO-001 local operator evidence showed 6 jobs could be made `rankable` after fresh detail/assessment and evidence-backed review, but only one was above the approved 70/100 recommendation threshold. That proof is local runtime evidence, not shipped DB state.

This distinction is now central to Product Recovery:

- repository/CI proof protects contracts;
- local DB/live HTTP/provider proof establishes runtime behavior;
- operator acceptance decides whether visible product output is useful.

## Post-migration workspace state

`POST-MIGRATION-RESTART = PASS` remains valid retained proof from 2026-09-02.

Canonical workspace discipline:

- persistent checkout: `$HOME/projects/job-application-pipeline` on clean `main`;
- feature worktrees: `$HOME/worktrees/job-application-pipeline/<feature>`;
- feature work starts from fresh remote `main`;
- project feature worktrees do not belong under `/tmp`;
- runner workspaces remain execution-only;
- branch-of-branch continuation is forbidden.

Dirty/divergent/ambiguous state is preserve-by-default. DRJ/retention debt alone is not unrelated project work-admission authority.

## Mandatory read order

1. `product.md`
2. `../reference/product-contract/PRD.md`
3. `../reference/product-contract/PRODUCT_DECISION_REGISTER.md`
4. `architecture.md`
5. `pipeline.md`
6. `system-diagrams.md`
7. `governance.md`
8. `operations.md`
9. `../planning/active/product_recovery_001.md`
10. issue `#783`
11. retained DEMO-001 evidence when needed: `../planning/active/demo_001_live_e2e_reentry.md`
12. retained ACQ-676 context only when relevant: `../planning/active/acq_generalization_90_reentry.md`

## Re-entry rule

Re-entry restores continuation from durable truth; it does not replay business side effects to reconstruct a previous chat narrative.

Before mutation:

- authenticate repository ID/main/workspace;
- inspect current active issue/PR/CI;
- inspect DB/live evidence when runtime claims matter;
- reconcile any conflict with older summaries;
- resume from the newest legal durable state.
