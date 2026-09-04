# Current Truth

Status: current truth navigation

This folder contains the small maintained surface for the current product. It is intentionally not a complete history.

## Re-entry source authority

Every re-entry starts from this current-truth surface read from canonical `refs/heads/main`.
A branch-local copy of `docs/current/*`, a branch-local planning document, an old checkout, or a familiar worktree may describe active work but is **not** allowed to redefine canonical `main`, canonical checkout role, or re-entry authority.

Repository-owned project hygiene and DRJ policy remain authoritative for workspace paths, prevention rules, and retention handoff:

- `PROJECT-HYGIENE.json` is project hygiene authority;
- `PROJECT-LOCAL-WORKSPACE.json` declares bounded canonical checkout/worktree roots;
- `PROJECT-DRJ.json` defines retention/reconciliation boundaries and explicitly does **not** make DRJ project work-admission authority;
- `POST-MIGRATION-RESTART.json` is the one-time project restart checkpoint under the shared portfolio contract.

## Post-migration restart state

This repository reached **`POST-MIGRATION-RESTART = PASS`** on 2026-09-02 after exact host counter-inspection, ancestry-free harvest and local retirement proof.

Canonical local invariant now proven:

- exactly one persistent project checkout remains at `$HOME/projects/job-application-pipeline`;
- that checkout is clean `main` and equals fresh remote `main` at the recorded proof point;
- no non-main project worktree remains;
- no local non-main project branch remains;
- all discovered unique value was integrated onto current-main ancestry or durably classified/preserved;
- no remote branch was deleted as part of the local restart proof.

Durable evidence:

- `POST-MIGRATION-RESTART.json`;
- issue `#704`;
- `docs/knowledge/branch_salvage_704.md`;
- PR `#705` / merge `41c855c3858b40a3d2d1d7b84dc8d6488f81d2a9`.

A project-local `POST-MIGRATION-RESTART = PASS` restores normal work admission for that project under canonical-main + declared temporary-worktree discipline. Other projects' unfinished restart state is not authority to stop this already-PASS project. Portfolio all-PASS remains a prerequisite only for separately coordinated portfolio-wide Warmrunner/DRJ/convergence steps.

## Salvaged product checkpoint — DEMO-001

DEMO-001 / issue `#707` is now a **salvaged product checkpoint**, not the long-term sequencing authority.

The proven demo slice was merged to `main` by PR `#781` / merge `d63ba7125693b19286d93b8d32bd955581ac84cd`.

The retained vertical journey remains:

`discovery / market evidence -> employer + origin -> connector/source health -> Bronze -> Silver -> Gold / Product V1 -> authoritative ranking -> selected job -> Application Workspace -> source-grounded draft_for_review`.

The salvage established durable product value around Employer-Origin action truth, live vacancy freshness/detail refresh, rankable refill/review tooling, Product Truth frontend runtime hardening, provider-backed application drafting and local DOCX/PDF/ZIP packaging. It also exposed integration debt that must not be hidden by further demo-only work.

The existing React Control Center remains the reference product UI. No fake Product V1 rows, fabricated ranking fill, weakened origin authority, automatic application submission, or demo-only success branch is allowed.

Canonical retained demo anchor:

- `../planning/active/demo_001_live_e2e_reentry.md`.

## Release management

GitHub Releases are now the product-facing change history.

Release management was merged by PR `#782` / merge `1acb4b4acc5016b25b8115ef048185448b1d76dc`.

Canonical release surfaces:

- `.github/RELEASE_MANAGEMENT.md` — versioning, release authority and release-note contract;
- `.github/release.yml` — generated release-note categories, including explicit bug-fix grouping;
- `.github/workflows/release.yml` — guarded `main`-only release workflow with exact-SHA CI/re-entry gates;
- `.github/release-notes/v0.1.0-demo.1.md` — curated first demo milestone notes.

Commit history remains engineering detail. Product-visible checkpoints must be represented by GitHub Releases with features, bug fixes, known limitations and relevant operator proof.

## Active product continuation — PRODUCT-RECOVERY-001

The current product priority is **PRODUCT-RECOVERY-001 / issue #783**.

The optimization target is no longer additional subsystem hardening by default. The primary product truth is one repeatable cold-to-application flow:

`market discovery -> Employer-Origin resolution -> current exact vacancy -> Bronze -> Silver -> assessment -> capability fit -> hard filter -> deterministic ranking -> >=5 current Employer-Origin recommendations -> Application Workspace -> review-ready CV/letter package`.

Primary acceptance metric:

**5 current Employer-Origin jobs -> assessed -> rankable/recommended -> application-ready**.

The path must be reproducible without demo-only rows, stale aggregator action URLs, fabricated freshness, ranking overrides, or manual repair campaigns between normal stages.

Recovery priorities are:

1. propagate discovery vs Employer-Origin truth consistently end to end;
2. enforce freshness before ranking/recommendation;
3. converge repair/refill helpers into one normal operator product flow;
4. increase rankable throughput by removing integration bottlenecks rather than lowering gates;
5. raise application document content/layout to near-submission quality;
6. inventory and reduce overlapping views, runners, policies and recovery paths that do not contribute to the primary product truth;
7. protect each product checkpoint through CI/E2E proof and GitHub Releases.

Until this core path is stable, broad new deterministic hardening, ML expansion beyond already-approved foundation work, post-application expansion and new demo-only orchestration are deprioritized.

## Pipeline Development Navigator — diagnostic sidecar

The **Pipeline Development Navigator** is a project-local operator/developer aid for understanding where active engineering sits inside the product E2E. It is deliberately a **sidecar**, not a product-work authority.

Hard contract:

- the navigator is read-only/derived from existing product, runtime, issue and E2E evidence;
- it may never become a CI gate, merge gate, re-entry gate, work-admission authority or prerequisite for continuing the E2E;
- when navigator maintenance conflicts with product progress, product E2E work wins immediately;
- navigator updates should be harvested opportunistically while a transition is already being touched, not developed as a separate campaign;
- it must distinguish **horizontal product progress** from a **vertical capability spike** required to unblock one horizontal transition;
- a vertical spike must always declare the horizontal return condition so that local debugging cannot silently replace the end-to-end goal.

Canonical horizontal product journey:

`market discovery -> Employer-Origin -> current exact vacancy -> Bronze -> Silver -> assessment -> capability fit -> hard filter -> deterministic ranking -> UI recommendation -> Application Workspace -> review-ready package`.

Navigator movement values:

- `HORIZONTAL` — advancing the same subject through the canonical product journey;
- `VERTICAL_SPIKE` — implementing or proving a reusable capability at the current horizontal transition;
- `RETURNING_HORIZONTAL` — the vertical capability has produced the evidence needed to resume the product journey.

Navigator stage status values:

- `PROVEN` — the current E2E subject has live evidence for the transition;
- `ACTIVE` — the current horizontal transition being pursued;
- `SPIKE` — the active reusable capability nested under that transition;
- `PENDING` — not yet traversed by the current subject;
- `BLOCKED` — attempted and concretely blocked; must include the observed reason and next safe action.

Minimum operator fields:

```text
CAMPAIGN
SUBJECT
MOVEMENT
HORIZONTAL_POSITION
VERTICAL_CAPABILITY
RETURN_CONDITION
```

Current E2E navigator snapshot at the time of this branch work:

```text
CAMPAIGN            E2E-SLICE-001 / issue #794 under PRODUCT-RECOVERY-001 / #783
SUBJECT             VALUNY GmbH
MOVEMENT            VERTICAL_SPIKE
HORIZONTAL_POSITION Employer-Origin -> current exact vacancy
VERTICAL_CAPABILITY B-ITE provider / tenant vacancy acquisition
RETURN_CONDITION    one current VALUNY Employer-Origin vacancy is acquired from the
                    employer-authorized B-ITE path; then resume horizontally at Bronze

[PROVEN] Market discovery
[PROVEN] Employer-Origin
[ACTIVE] Current exact vacancy acquisition
         [PROVEN] VALUNY first-party career/listing surface
         [PROVEN] employer-backed B-ITE loader binding
         [PROVEN] tenant/listing binding: spectrumk:spectrumk-listing-2026
         [PROVEN] B-ITE customer asset reachable
         [PROVEN] B-ITE API v5 runtime reachable
         [PROVEN] POST/JSON transport contract and jobs.b-ite.com search service observed
         [SPIKE ] exact live vacancy retrieval
[PENDING] Bronze
[PENDING] Silver
[PENDING] Assessment / capability fit
[PENDING] Hard filter
[PENDING] Deterministic ranking
[PENDING] UI recommendation
[PENDING] Application Workspace
[PENDING] Review-ready CV/letter package
```

This snapshot is diagnostic context, not an alternative project truth. If later live evidence has moved the E2E forward, re-entry must update or supersede the snapshot rather than treating stale navigator text as a reason to repeat already-proven work.

Operator blocks may render the navigator as a compact header when useful. Rendering is optional and must not add network calls, database writes or product mutations merely to display status.

## Preserved deterministic continuation

**ACQ-GENERALIZATION-90 / issue #676** remains retained and resumable, but it is not the current product sequencing authority. This is a priority pause, not a stop, rejection, or supersession.

Its retained anchors remain:

- `../planning/active/acq_generalization_90_reentry.md`;
- `../planning/active/acq_generalization_90_reentry.json`;
- `../planning/active/acq_generalization_90_target.md`;
- `../planning/active/acq676_external_deterministic_salvage.md`.

When the operator returns to ACQ-676, the next measured deterministic action remains the same 65-candidate V6 benchmark. Product coverage remains `36/65` until materialized unchanged strict E2E proof establishes a higher numerator.

The older `REENTRY-001B` / issue #672 material remains predecessor evidence, not current sequencing authority.

## Mandatory workspace hygiene on every re-entry

Even after the one-time restart PASS, every new re-entry must freshly prove the direct workspace conditions relevant to the next action:

- canonical path, repository identity, origin, branch, HEAD and upstream state;
- canonical persistent checkout is clean `main`;
- feature work starts from fresh remote `main` in the declared temporary-worktree root;
- branch-of-branch continuation is forbidden;
- dirty, divergent, unpushed, detached, locked/in-use, closed-unmerged or ambiguous state is preserve-by-default and fails closed only for directly affected work;
- clean retention debt is surfaced for reconciliation but does not by itself block unrelated project work;
- `RETENTION_DEBT`, `RECONCILIATION_PENDING`, missing DRJ `CHECK=PASS`, or DRJ unavailability alone are not project work-admission blockers;
- age, path, name, merge-looking status or repository pressure never establish deletion authority.

Runner workspaces remain execution-only and are not project worktrees.

Read in this order:

1. `product.md`
2. `architecture.md`
3. `pipeline.md`
4. `system-diagrams.md`
5. `governance.md`
6. `operations.md`
7. `POST-MIGRATION-RESTART.json`
8. while issue #783 is active priority: issue `#783` plus this current-truth section, including the Pipeline Development Navigator contract/snapshot
9. retained DEMO-001 evidence when needed: `../planning/active/demo_001_live_e2e_reentry.md`
10. retained ACQ-676 context when needed: `../planning/active/acq_generalization_90_reentry.md`
