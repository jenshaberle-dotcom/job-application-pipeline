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

The shared portfolio restart contract still requires all ten managed projects to reach `PASS` before active project development resumes. This repository's local restart gate no longer blocks, but portfolio sequencing remains authoritative until the all-PASS condition is satisfied.

## Active acquisition continuation

The current deterministic acquisition-hardening continuation is **ACQ-GENERALIZATION-90 / issue #676**.

Its canonical anchors are:

- `../planning/active/acq_generalization_90_reentry.md` — current semantic continuation;
- `../planning/active/acq_generalization_90_reentry.json` — machine-readable state;
- `../planning/active/acq_generalization_90_target.md` — full-population metric and guardrails;
- `../planning/active/acq676_external_deterministic_salvage.md` — V6 external/historical provider capability map.

The next ACQ-676 engineering measurement is the **same 65-candidate V6 benchmark** after portfolio all-PASS restart authority. V6 is already merged; product coverage remains `36/65` until materialized unchanged strict E2E proof establishes a higher numerator.

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
8. when issue #676 is active: `../planning/active/acq_generalization_90_reentry.md`
