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

## Active product continuation — E2E-FOCUS-001 / PRODUCT-RECOVERY-001

The current product priority is **E2E-FOCUS-001 / issue #783** (former working title `PRODUCT-RECOVERY-001`).

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

## CI-max execution boundary

Routine deterministic Product/DB continuation uses the Trusted Local Product CI contract in `ci-max-execution.md` and `.github/workflows/trusted-local-product-campaign.yml`.

The execution boundary is deliberately split:

- GitHub-hosted admission may authenticate and reject stale/invalid requests before scarce local execution is requested;
- Product/DB execution that requires the local `.env` and PostgreSQL remains on the trusted self-hosted Linux runtime surface;
- GitHub-hosted execution is not a fallback for local Product/DB mutation;
- the hosted B-ITE read-only probe introduced by PR `#798` is a bounded evidence surface only and does not provide local DB access;
- a warmrunner profile being provisioned/migrated is not proof that the runner is currently online or routable; execution capacity must be established from fresh heartbeat/route evidence before any wake/retry decision;
- do not replay an already-triggered Product campaign merely because a chat/context interruption occurred. First classify the newest Actions/runtime state and preserve completed admission or mutation evidence.

At the `main@fc70ecb9d315a92e49139a07f3d3e9a7f50cc79d` reconciliation point, PR `#798` explicitly records unavailable local warm capacity as the reason for adding the independent hosted read-only B-ITE proof. Issue `#794` contains Product-campaign trigger requests for VALUNY candidate `83`, but the comments themselves are not execution-completion evidence.

Fresh exact-head route evidence from PR `#799` / Pipeline CI run `#1245` at `2026-09-04T14:00:00Z` resolved the current CI route as:

```text
WARM_LABELS=["self-hosted","Linux","X64","job-pipeline-runtime-linux"]
ROUTE=github-hosted
REASON=no-successful-heartbeat
```

Therefore the current trusted Linux Product/DB execution surface is **not routable under the canonical warm-route contract**. This establishes the operational blocker, not its service-level root cause. A provisioned/sleep-capable warmrunner profile must not be mistaken for current capacity, and hosted CI must not be promoted into a DB-mutation fallback.

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

Current E2E navigator snapshot reconciled to canonical `main@fc70ecb9d315a92e49139a07f3d3e9a7f50cc79d` and durable issue `#794` evidence:

```text
CAMPAIGN            E2E-SLICE-001 / issue #794 under E2E-FOCUS-001 / #783
SUBJECT             VALUNY GmbH / employer-origin candidate 83
MOVEMENT            RETURNING_HORIZONTAL
HORIZONTAL_POSITION Employer-Origin candidate -> connectorized current vacancy -> Bronze
VERTICAL_CAPABILITY B-ITE provider / tenant vacancy acquisition — PROVEN diagnostically
RETURN_CONDITION    carry the learned B-ITE contract through the normal generic connector
                    auto-generation + fixture/test-plane contract, then acquire the real
                    current VALUNY vacancy through that connectorized path; only then Bronze
EXECUTION_CAPACITY  BLOCKED — warm route unavailable: no-successful-heartbeat

[PROVEN] Market discovery
[PROVEN] Fresh-company reservation / immutable discovery evidence
[PROVEN] Canonical Employer-Origin candidate ingress: id=83, company_key=valuny
[PROVEN] Employer-owned VALUNY career/listing surface
[PROVEN] Employer-backed B-ITE loader binding
[PROVEN] Tenant/listing binding: spectrumk:spectrumk-listing-2026
[PROVEN] B-ITE customer asset and API-v5 runtime contract
[PROVEN] Exact current VALUNY vacancy through bounded exploratory B-ITE proof
[ACTIVE] Normal Employer-Origin / connectorized acquisition continuation
         [BLOCKED] DB-backed Employer-Origin gate progression for candidate 83
                   operational blocker: job-pipeline-runtime-linux not routable
         [PENDING] generic B-ITE connector auto-generation / fixture contract proof
         [PENDING] real current vacancy acquired through normal connectorized path
[PENDING] Bronze
[PENDING] Silver
[PENDING] Assessment / capability fit
[PENDING] Hard filter
[PENDING] Deterministic ranking
[PENDING] UI recommendation
[PENDING] Application Workspace
[PENDING] Review-ready CV/letter package
```

Important truth boundary: the exploratory B-ITE vacancy proof establishes that the real current vacancy exists and that the provider/tenant contract is usable. It does **not** authorize a direct `raw_jobs`/manual DB bypass and does not count as Bronze ingestion. The cold E2E still has to traverse the normal connectorized product path.

The exact next operational action is to inspect the newest Trusted Local Product Campaign admission/request state for candidate `83` and, when it is waiting only on `job-pipeline-runtime-linux`, restore that **existing** warm execution surface through its canonical RCC lifecycle. Do not create a replacement runner and do not route DB mutation to GitHub-hosted CI merely to bypass the heartbeat failure. After restoration, require a successful warm heartbeat/route proof before allowing the bounded Product campaign to execute. If the RCC wake/start path requires UAC or service authority, that is the operator boundary. If newer campaign evidence shows completion, rejection, staleness or a different classified blocker, preserve it and continue from that newer state instead of replaying the request.

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
7. `ci-max-execution.md`
8. `POST-MIGRATION-RESTART.json`
9. while issue #783 is active priority: issue `#783`, active slice issue `#794`, and this current-truth section including the Pipeline Development Navigator contract/snapshot
10. retained DEMO-001 evidence when needed: `../planning/active/demo_001_live_e2e_reentry.md`
11. retained ACQ-676 context when needed: `../planning/active/acq_generalization_90_reentry.md`
