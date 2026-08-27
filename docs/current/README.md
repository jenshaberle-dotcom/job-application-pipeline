# Current Truth

Status: current truth navigation

This folder contains the small maintained surface for the current product.
It is intentionally not a complete history.

## Re-entry source authority

Every re-entry starts from this current-truth surface read from canonical `refs/heads/main`.
A branch-local copy of `docs/current/*`, a branch-local planning document, an old checkout, or a familiar worktree may describe active work but is **not** allowed to redefine canonical `main`, canonical checkout role, or re-entry authority.

Repository-owned project hygiene is authoritative for local workspace paths and prevention rules:

- `PROJECT-HYGIENE.json` is the project hygiene authority;
- `PROJECT-LOCAL-WORKSPACE.json` is referenced by that contract and declares bounded canonical checkout/worktree roots;
- this re-entry surface may reference those paths but must not duplicate or redefine them.

## Mandatory re-entry workspace hygiene gate

Before reading current truth as continuation authority or executing any next action, first reconcile live local Git checkout/worktree topology against `PROJECT-HYGIENE.json`.

Hard invariant:

- exactly one persistent canonical checkout is allowed for this repository and it must be on the repository canonical/default branch (`main` unless live repository truth says otherwise);
- normal scanner/preflight scope is the declared canonical path bindings and temporary workspace roots; broad home/project scanning is fallback-only when repository workspace truth is missing, invalid or contradicted by host evidence;
- non-main branches may be locally checked out only while they are explicitly part of current active work and should be created under the declared temporary-workspace root;
- integrated chat/runner/manual-test creators should register a workspace lease/provenance record rather than create anonymous local state;
- closed, merged, superseded, abandoned, stale or otherwise inactive non-main local checkouts/worktrees must be surfaced for DRJ reconciliation before project continuation;
- path names, remembered roles, old PR state or long-lived local presence never make a branch canonical `main`;
- canonical path, repository identity, origin, current branch, HEAD and upstream state must be freshly proven;
- dirty, divergent, unpushed, locked/in-use, closed-unmerged or ambiguous local state is protected and must surface CHECK rather than be deleted;
- do not use `git reset --hard`, `git clean -fdx`, `git branch -D`, force checkout over unique state, or path/name/age-only worktree/clone deletion as automatic cleanup;
- after reconciliation, continue only when local topology is `canonical main + explicitly active/leased non-main workspaces only`.

Prevention target: normal CI and local fallback should create bounded, declared, lifecycle-aware workspaces so DRJ mostly verifies hygiene and only performs exceptional reconciliation when lifecycle closure fails.

This gate is mandatory on every re-entry and precedes the normal current-truth read order below.

Read in this order:

1. `product.md`
2. `architecture.md`
3. `pipeline.md`
4. `system-diagrams.md`
5. `governance.md`
6. `operations.md`
