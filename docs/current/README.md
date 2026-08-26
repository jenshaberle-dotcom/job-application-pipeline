# Current Truth

Status: current truth navigation

This folder contains the small maintained surface for the current product.
It is intentionally not a complete history.

## Re-entry source authority

Every re-entry starts from this current-truth surface read from canonical `refs/heads/main`.
A branch-local copy of `docs/current/*`, a branch-local planning document, an old checkout, or a familiar worktree may describe active work but is **not** allowed to redefine canonical `main`, canonical checkout role, or re-entry authority.

## Mandatory re-entry workspace hygiene gate

Before reading current truth as continuation authority or executing any next action, first reconcile live local Git checkout/worktree topology.

Hard invariant:

- exactly one persistent canonical checkout is allowed for this repository and it must be on the repository canonical/default branch (`main` unless live repository truth says otherwise);
- non-main branches may be locally checked out only while they are explicitly part of current active work;
- closed, merged, superseded, abandoned, stale or otherwise inactive non-main local checkouts/worktrees must be retired before project continuation;
- path names, remembered roles, old PR state or long-lived local presence never make a branch canonical `main`;
- canonical path, repository identity, origin, current branch, HEAD and upstream state must be freshly proven;
- dirty, divergent, unpushed, locked/in-use, closed-unmerged or ambiguous local state is protected and must surface CHECK rather than be deleted;
- do not use `git reset --hard`, `git clean -fdx`, `git branch -D`, force checkout over unique state, or path/name/age-only worktree/clone deletion as automatic cleanup;
- after cleanup, re-inventory and continue only when local topology is `canonical main + explicitly active non-main worktrees only`.

This gate is mandatory on every re-entry and precedes the normal current-truth read order below.

Read in this order:

1. `product.md`
2. `architecture.md`
3. `pipeline.md`
4. `system-diagrams.md`
5. `governance.md`
6. `operations.md`
