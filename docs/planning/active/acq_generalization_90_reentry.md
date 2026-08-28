# ACQ-GENERALIZATION-90 — canonical re-entry after workspace migration

Status: **ACTIVE — MIGRATION COMPLETE**  
Owner issue: `#676`  
Active draft PR: `#682`  
Active branch: `agent/676-generalization-harvest`  
Canonical base: `main@7644f587d3bd3eb51310451608b7ceb5255ef859`

Machine-readable companion: `docs/planning/active/acq_generalization_90_reentry.json`.

## Authority

This file is the active ACQ-676 continuation anchor. It is subordinate to
`PROJECT-HYGIENE.json`, `PROJECT-LOCAL-WORKSPACE.json`, `PROJECT-DRJ.json`, and the
product/current-truth surfaces, but supersedes the old migration-pause resume text
for ACQ-676 sequencing.

Repository truth, live bounded evidence, tests and CI override chat summaries.

## Migration completion proof

The canonical workspace migration is complete for ACQ-676.

The qualified old #676 content from superseded PR `#678` was harvested without
importing the old branch ancestry:

- old source head: `14e60cd24cfdcc37a41ef9171e6ce269553c69ed`;
- new harvest commit: `6850f4f96186e189165ca8f588752c443847e6ad`;
- harvest parent count: exactly one;
- sole parent: canonical `main@7644f587d3bd3eb51310451608b7ceb5255ef859`;
- harvested diff: exactly 23 qualified files (`22 added`, `1 modified`);
- old PR `#678`: closed as superseded, never merged;
- new PR `#682`: active continuation PR.

The original migration checkpoint remains immutable historical provenance:

- `acq_generalization_90_migration_checkpoint_20260828.md`;
- `acq_generalization_90_migration_checkpoint_20260828.json`.

Those files are **not stale disposable migration debris** while ACQ-676 is active.
They contain exact historical cohorts, metric baselines and the pre-migration live
Clarios trace needed to interpret later A/B results.

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

### Completed after migration

The Clarios proof failure was narrowed to the public Workday SPA proof surface. The
unchanged canonical proof itself was not weakened.

A generic same-host Workday CXS detail projection now exists:

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

Qualified Workday code checkpoint:

- code head `ae8b272f23f148df786e776b4b6caa57002a4da0`;
- Pipeline CI `#875`: success;
- Re-entry `#1420`: success.

A V4 builder overlay exists and may promote **only** an existing Inventory first
failure after the strict Workday path succeeds. It is intentionally monotonic and
cannot rewrite Origin, Detail or Proof failures.

### Current residual slice

The first-party -> portal vocabulary residual is being addressed without globally
widening `LISTING_TEXT_MARKERS`.

Current public Bahlsen evidence still exposes `karriere.bahlsen.com` behind the
strong CTAs `Jetzt einen Job finden` and `Zum Jobportal`. The generic bridge accepts
only explicit strong portal CTAs whose destination is additionally bound by same
registered employer domain or a career/jobs host label. Multiple qualifying portal
URLs fail closed.

Active implementation files:

- `src/connectors/employer_origin_portal_delegation.py`;
- `src/connectors/employer_origin_portal_delegation_acquisition.py`;
- `tests/test_employer_origin_portal_delegation.py`.

This is a reusable delegation class, not a Bahlsen-specific success path.

## Sole continuation sequence

1. Keep #682 and `agent/676-generalization-harvest` active until the current changes
   are merged or intentionally superseded by another ancestry-clean branch from
   current `origin/main`.
2. Run/review complete CI for every current #682 head before treating a new slice as
   qualified.
3. From the canonical WSL runtime/database, run the same 65-candidate V4 builder
   replay and record Workday promotions without changing the product numerator.
4. Qualify the bounded portal-delegation bridge; then compose it as a monotonic
   overlay on residual Inventory failures and replay the same cohort.
5. Re-cluster the remaining first-failure population after each measured generic
   lift. Prefer reusable classes over named-employer rescue work.
6. Materialize connector recipes only after diagnostic classes are stable and then
   use unchanged strict E2E proof to update the canonical numerator.
7. Continue deterministic hardening until no evidence-backed bounded generic class
   remains; only then admit residuals to the booster path.

## Retention / DRJ semantic dispositions

Project semantic authority explicitly assigns the following dispositions while
ACQ-676 remains open:

### ACTIVE / KEEP

- issue `#676`;
- draft PR `#682`;
- branch `agent/676-generalization-harvest` while #682 is open/current;
- `docs/planning/active/acq_generalization_90_target.md`;
- this re-entry file and its JSON companion;
- `docs/planning/active/deterministic_connector_builder_layers.md`;
- all currently referenced ACQ-676 builder, Origin V2, Workday, portal-delegation,
  audit and focused regression-test source files in #682.

These items must not be classified as retention candidates merely because they are
new, branch-local, migration-related, diagnostic, or not yet materialized into the
product numerator.

### PRESERVE — historical provenance still semantically required

- `acq_generalization_90_migration_checkpoint_20260828.md`;
- `acq_generalization_90_migration_checkpoint_20260828.json`;
- issue/PR comments that contain the exact live 65-candidate A/B counts and Clarios
  request trace.

Do not delete or rewrite these based on age/path/name. They remain the comparison
baseline until ACQ-676 is closed with a final durable outcome record.

### SUPERSEDED / RETIRE only after exact harvest condition

- old PR `#678`: already SUPERSEDED and closed;
- old branch `agent/676-deterministic-connector-builder`: may become an exact RETIRE
  candidate **only after #682 is merged to canonical main and the harvested 23-file
  content plus later retained ACQ-676 content is verified present on main**.

Old branch ancestry has no semantic preservation requirement after that condition;
its qualified content does.

### DISPOSABLE / not repository truth

The former `/tmp/deterministic_*` audit artifacts listed in the migration checkpoint
are not required for retention. Their relevant result truth was versioned into the
checkpoint/re-entry documents. They may disappear without semantic loss.

## DRJ effect boundary during active work

`DRJ-RECONCILE-REQUEST.json` should remain `NO_REQUEST` for ACQ-676 branch deletion
while #682 is active. Do not publish a branch-retirement effect request merely
because #678 is closed or the old branch is aged. The exact safe-retirement
condition is #682 merged + content verified on canonical main.

DRJ remains retention/reconciliation infrastructure, not ACQ-676 work-admission
authority. Dirty, unique, divergent, ambiguous or closed-unmerged state remains
protected according to `PROJECT-DRJ.json`.

## Re-entry commandment

On every later continuation, read in this order before editing ACQ-676:

1. `PROJECT-HYGIENE.json`;
2. `PROJECT-LOCAL-WORKSPACE.json`;
3. `PROJECT-DRJ.json`;
4. `docs/current/README.md`;
5. this file;
6. `acq_generalization_90_target.md`;
7. live issue `#676` and PR `#682` state;
8. current branch/main relationship and latest CI.

Do not resume from the old #678 branch or from chat memory.
