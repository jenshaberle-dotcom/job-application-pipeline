# ACQ-GENERALIZATION-90 — canonical re-entry

Status: **ACTIVE — WORKSPACE MIGRATION MERGED TO MAIN**  
Owner issue: `#676`  
Canonical main at migration closure: `6af34cb54a9bbf29ffc257d1109f495d08d1678d`

Machine-readable companion: `docs/planning/active/acq_generalization_90_reentry.json`.

## Authority

This file is the active ACQ-676 continuation anchor. It is subordinate to
`PROJECT-HYGIENE.json`, `PROJECT-LOCAL-WORKSPACE.json`, `PROJECT-DRJ.json`, and the
product/current-truth surfaces.

Repository truth, live bounded evidence, tests and CI override chat summaries.

Do not hard-code a feature branch as long-lived continuation authority. Every new
mutating ACQ-676 slice must start from freshly observed current `origin/main` in a
declared worktree/feature branch. Resolve the current open PR from live GitHub state.

## Migration closure proof

The 2026-08-28 canonical workspace migration is fully delivered to `main`.

Qualified old #676 content from superseded PR `#678` was harvested without importing
old branch ancestry:

- old source head: `14e60cd24cfdcc37a41ef9171e6ce269553c69ed`;
- ancestry-free harvest commit: `6850f4f96186e189165ca8f588752c443847e6ad`;
- harvest parent count: exactly one;
- harvest parent: `main@7644f587d3bd3eb51310451608b7ceb5255ef859`;
- harvested diff: exactly 23 qualified files (`22 added`, `1 modified`);
- old PR `#678`: closed, superseded, never merged;
- delivery PR `#682`: merged;
- delivery merge commit on canonical main: `6af34cb54a9bbf29ffc257d1109f495d08d1678d`;
- delivery merge tree equals the fully green #682 head tree, so the complete 37-file
  ACQ-676 migration/generalization state is present on canonical main.

Final #682 pre-merge gates:

- Pipeline CI `#883`: success;
- Re-entry `#1436`: success;
- merge base before merge: exact canonical `main@7644f587d3bd3eb51310451608b7ceb5255ef859`;
- branch state before merge: `ahead 15`, `behind 0`;
- unresolved review threads: `0`.

The original migration checkpoint remains immutable historical provenance:

- `acq_generalization_90_migration_checkpoint_20260828.md`;
- `acq_generalization_90_migration_checkpoint_20260828.json`.

Those files are **not disposable migration debris**. They contain exact historical
cohorts, metric baselines and the pre-migration live Clarios trace needed to
interpret later A/B results.

## Canonical metric remains unchanged

Current product numerator remains:

`36 / 65 = 55.4%`

Target at the current denominator:

`>= 59 / 65 = 90.8%`

Builder `recipe_ready` is diagnostic only. No Workday or portal-bridge work may be
counted in the product numerator until a materialized connector passes unchanged
strict E2E acquisition proof.

## Qualified engineering frontier

### Completed before migration

Do not repeat unless repository/network truth materially changed:

- full fresh-10 root-cause analysis;
- balanced Origin V2 breadth-first planner;
- Origin first-failures `18 -> 8` with no earlier-stage regression;
- inventory surface audit and inventory bridge audit;
- V3 provider-inventory composition;
- V3 Inventory first-failures `17 -> 16`;
- exact V3 65-candidate failure cohorts;
- historical Workday route recovery;
- live Clarios chain through employer authority -> Workday board -> CXS inventory -> concrete public detail.

### Workday proof/acquisition — merged and qualified

The Clarios proof failure was narrowed to the public Workday SPA proof surface. The
unchanged canonical proof itself was not weakened.

A generic same-host Workday CXS detail projection exists:

`public externalPath -> exact /wday/cxs/<tenant>/<site>/job/... -> jobPostingInfo content -> PageSnapshot -> unchanged genuine_job_detail_proof`

The production-shaped generic Workday acquisition composition is:

`authorized employer/Workday root -> exact CXS inventory POST -> same-board externalPath -> exact same-host CXS detail GET -> unchanged genuine_job_detail_proof`

Properties:

- no tenant/site/job identity guessing;
- no company-specific success branch;
- public SPA job URL remains the returned canonical job URL;
- raw `jobPostingInfo` wrapper metadata is excluded from proof projection;
- successful delegated route requires only three injected requests;
- no provider, LLM or Tavily request;
- no DB/source/Bronze/Silver/Product writes;
- no connector materialization.

A V4 builder overlay is merged and may promote **only** an existing Inventory first
failure after strict Workday proof. It cannot rewrite Origin, Detail or Proof failures.

Qualified pre-merge Workday checkpoint:

- code head `ae8b272f23f148df786e776b4b6caa57002a4da0`;
- Pipeline CI `#875`: success;
- Re-entry `#1420`: success.

The complete delivery containing that work is now on `main@6af34cb54a9bbf29ffc257d1109f495d08d1678d`.

### Evidence-bounded portal delegation — merged

The first-party -> portal vocabulary residual is addressed without globally widening
`LISTING_TEXT_MARKERS`.

Current public Bahlsen evidence exposed `karriere.bahlsen.com` behind the strong CTAs
`Jetzt einen Job finden` and `Zum Jobportal`. The generic bridge accepts only
explicit strong portal CTAs whose destination is additionally bound by same
registered employer domain or a career/jobs host label. Multiple qualifying portal
URLs fail closed.

Merged implementation files:

- `src/connectors/employer_origin_portal_delegation.py`;
- `src/connectors/employer_origin_portal_delegation_acquisition.py`;
- `tests/test_employer_origin_portal_delegation.py`.

This is a reusable delegation class, not a Bahlsen-specific success path.

## Sole continuation sequence

1. From the canonical WSL runtime/database, run the same 65-candidate V4 builder
   replay and record Workday promotions without changing the product numerator.
2. Compose the already-merged bounded portal-delegation bridge as a monotonic overlay
   on residual Inventory failures and replay the same cohort.
3. Re-cluster the remaining first-failure population after each measured generic
   lift. Prefer reusable classes over named-employer rescue work.
4. Materialize connector recipes only after diagnostic classes are stable and then
   use unchanged strict E2E proof to update the canonical numerator.
5. Continue deterministic hardening until no evidence-backed bounded generic class
   remains; only then admit residuals to the booster path.

Any code change for these steps must branch from the **then-current** `origin/main`,
not from either historical #676 feature branch.

## Retention / DRJ semantic dispositions

Project semantic authority explicitly assigns the following dispositions while
ACQ-676 remains open.

### ACTIVE / KEEP

- issue `#676`;
- canonical `main` content delivered by PR `#682`;
- `docs/planning/active/acq_generalization_90_target.md`;
- this re-entry file and its JSON companion;
- `docs/planning/active/deterministic_connector_builder_layers.md`;
- all merged ACQ-676 builder, Origin V2, Workday, portal-delegation, audit and focused
  regression-test files referenced by this re-entry.

These items must not be classified as retention candidates merely because they are
diagnostic, migration-originated, or not yet credited to the product numerator.

### PRESERVE — historical provenance still semantically required

- `acq_generalization_90_migration_checkpoint_20260828.md`;
- `acq_generalization_90_migration_checkpoint_20260828.json`;
- issue/PR comments containing exact live 65-candidate A/B counts and Clarios request
  traces;
- PR `#682` discussion/merge history as migration-delivery provenance.

Do not delete or rewrite these based on age/path/name. They remain the comparison
baseline until ACQ-676 is closed with a final durable outcome record.

### SUPERSEDED / no continuation authority

- PR `#678` and branch `agent/676-deterministic-connector-builder`;
- merged delivery PR `#682` and branch `agent/676-generalization-harvest`.

Neither branch may be used for new feature work. Their qualified content is already
on canonical main.

Remote/local branch or worktree retirement is a **separate DRJ technical action**.
No destructive request is implied by the semantic `SUPERSEDED` classification.

### DISPOSABLE / not repository truth

The former `/tmp/deterministic_*` audit artifacts listed in the migration checkpoint
are not required for retention. Their relevant result truth was versioned into
repository documents. They may disappear without semantic loss.

## DRJ effect boundary after migration

`DRJ-RECONCILE-REQUEST.json` remains `NO_REQUEST` intentionally at migration closure.
Reason: repository content is safely merged, but this chat has not freshly observed
local branch/worktree dirtiness, unpushed state or checked-out state. The DRJ contract
requires those conditions to fail closed and treats closed-unmerged state as a
preservation/review condition.

A later re-entry hygiene pass may publish exact retirement candidates only after
fresh local observation. That cleanup is **not** required for project work admission
and does not affect the completed migration.

DRJ remains retention/reconciliation infrastructure, not ACQ-676 work-admission
authority.

## Re-entry commandment

On every later continuation, read in this order before editing ACQ-676:

1. `PROJECT-HYGIENE.json`;
2. `PROJECT-LOCAL-WORKSPACE.json`;
3. `PROJECT-DRJ.json`;
4. `docs/current/README.md`;
5. this file;
6. `acq_generalization_90_target.md`;
7. live issue `#676` and current open PR state;
8. current `origin/main`, branch/worktree relationship and latest CI.

Do not resume from PR #678, PR #682's merged branch, or chat memory.
