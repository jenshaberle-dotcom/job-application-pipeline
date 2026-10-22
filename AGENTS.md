# Agent entry — JAP Classic

**Scope: WSL host development. This is a fail-closed instruction, not optional advice.**

## Read-first authority

1. Read `PROJECT-REENTRY.json`, `PROJECT-LOCAL-WORKSPACE.json`, `POST-MIGRATION-RESTART.json`, the referenced native re-entry and `docs/current/WORKCHAT-REENTRY-20261022.md`.
2. Observe fresh GitHub repository and PR heads. Dated chat/history is not current source authority.
3. Run `python3 tools/workchat_workspace_gate.py --phase before-edit` **from the actual WSL worktree** before any source mutation, command that writes repository files, commit or push. If blocked, stop instead of creating a fallback clone.

## Filesystem isolation

- Sole persistent project checkout: `$HOME/projects/job-application-pipeline` (clean, current `main`, read/test only).
- All editable work: registered, named branch worktrees below `$HOME/worktrees/job-application-pipeline/`.
- Windows `Documents/Codex`, `%USERPROFILE%/repos`, other persistent clones, `/tmp` and runner execution directories are **not** project-workspace authority. Preserve old data for differential harvest; never treat it as a new checkout.
- Do not develop on `main`, revive old merged branches, create a branch from another feature branch or overwrite unresolved worktrees.
- Cloud Work or Windows-only execution without direct access to the declared WSL workspace must **STOP** before mutating. Repository metadata discussion through connected GitHub is a distinct, explicitly bounded operation, never proof of local editing.

## Delivery and token-exhaustion safety

- Before making a change, identify the one active slice, exact source/remote refs, pending effects and required approval. Check for existing dirty/unpushed work and salvage first.
- After each bounded coherent unit, run tests, commit on the declared branch, push **without force**, read back the exact `refs/heads/<branch>` SHA, then run `python3 tools/workchat_workspace_gate.py --phase after-push`.
- Do not postpone delivery until the final conversational message or token budget. A local commit without remote readback is **UNDELIVERED**.
- Do not blindly replay uncertain SQL writes, RCC claims, leases, dispatches, release/install or provider requests. Unit PASS, remote SHA, native qualification and product E2E are different evidence levels.
- Do not close/merge/delete active PRs or historical branches without exact-source semantic harvest, required CI/E2E acceptance and lifecycle absence checks. Do not invoke a second scheduler or runner authority.
- An agent may not claim actual path enforcement from this file or the guard alone: they are checks, **not an OS filesystem sandbox**. Until host-side Work sandbox/ACL admission is independently proved, keep `HOST_FILESYSTEM_ENFORCEMENT=UNVERIFIED` and block any claim of guaranteed containment.

## Current handoff

PR #1173, source 442ab273cb913d81c0cf196e6ed0faead8441352; 14 October 21 local commits have been recovered and pushed. Three untracked Launcher source files remain in the WSL recovery worktree.

Active operator decision restored Classic Connector Factory and job delivery; the September 30 Cloud-only freeze #1154 is superseded. Pipeline candidate daily budget is 20 new/retry firms plus 50 active sources; a retained backlog is not dropped. The code does not itself prove productive job ingest or UI projection. Avoid introducing a second timer: compare Runtime #399 with the RCC occurrence authority.

Current local test scope: 34 focused JAP Classic unit tests passed; database staging/rollback is not live product E2E.

Source-only documentation/workspace guard must itself be qualified and integrated before being treated as canonical `main` protection.
