# Agent entry — JAP Classic

**Scope: Work Cloud (GitHub connector only) or a positively approved WSL Work Local worktree. No Windows shadow clones. This is an admission contract, not a claim of an OS sandbox.**

## Read-first authority

1. Read `PROJECT-REENTRY.json`, `PROJECT-LOCAL-WORKSPACE.json`, `POST-MIGRATION-RESTART.json`, the referenced native re-entry and `docs/current/WORKCHAT-REENTRY-20261022.md`.
2. Observe fresh GitHub repository and PR heads. Dated chat/history is not current source authority.
3. Choose exactly **one** execution lane below before modifying anything; observe the live repository/PR head and the project's restart admission. For Local, run `python3 tools/workchat_workspace_gate.py --phase before-edit` from the actual WSL worktree; stop if blocked. For Cloud, enforce the repository/branch and remote-head checks through GitHub before every bounded commit.

## Work execution lanes (no silent fallback)

- **Preferred for source, documentation and harvest: Work Cloud / connected GitHub ONLY.** Use the authenticated GitHub connector to read, patch and commit an existing declared PR branch. Work must not request local-folder access, mount a Windows home directory, clone onto the operator host or treat a cloud scratch checkout as durable authority. An immutable remote commit with independently read-back SHA is the sole delivery checkpoint. Check the repository restart contract and obtain required source/CI admission; this does not grant native host-effect authority.
- **Only for indispensable host/local E2E: Work Local on the approved WSL project worktree.** The host must already restrict filesystem writes to the explicitly granted directories and deny Windows `Documents/Codex` shadow paths. Invoke the checked-in WSL pre-edit and after-push gates and perform a negative outside-root write probe under the actual Work execution identity before trusting containment. The local guard alone is NOT enforcement.
- **If local directory containment is unavailable or the actual execution environment is unknown:** use GitHub-only Cloud for source work, or stop for host-gated actions. NEVER 'fix' a missing WSL mount by cloning into `C:\Users\...\Documents\Codex`, `%USERPROFILE%\repos`, `/tmp` or a second persistent project root.
- **Cloud-host distinction:** transient cloud scratch code is not a host-local repository and has no source authority. It must be reproducible from the pushed GitHub SHA; work that depends on local installed services, secrets or DB is explicitly unverified and must not be simulated as production evidence.

## Filesystem isolation

- Sole persistent project checkout: `$HOME/projects/job-application-pipeline` (clean, current `main`, read/test only).
- All editable work: registered, named branch worktrees below `$HOME/worktrees/job-application-pipeline/`.
- Windows `Documents/Codex`, `%USERPROFILE%/repos`, other persistent clones, `/tmp` and runner execution directories are **not** project-workspace authority. Preserve old data for differential harvest; never treat it as a new checkout.
- Do not develop on `main`, revive old merged branches, create a branch from another feature branch or overwrite unresolved worktrees.
- Cloud Work **may** commit source-only changes directly through the connected GitHub API after project/branch/authority checks; it may **not** access or alter operator-local services, source trees, secrets, or runtime. Windows-only local Work without approved WSL root must STOP rather than clone.

## Delivery and token-exhaustion safety

- Before making a change, identify the one active slice, exact source/remote refs, pending effects and required approval. Check for existing dirty/unpushed work and salvage first.
- After each bounded coherent unit, run the available source tests, commit on the declared branch, and read back the exact remote `refs/heads/<branch>` SHA. **Cloud lane:** use GitHub's expected-head compare-and-swap update (no force) and read back the ref. **Local lane:** push without force and run `python3 tools/workchat_workspace_gate.py --phase after-push`. Do not mark tests or native host E2E as PASS without actual run evidence.
- Do not postpone delivery until the final conversational message or token budget. A local commit without remote readback is **UNDELIVERED**.
- Do not blindly replay uncertain SQL writes, RCC claims, leases, dispatches, release/install or provider requests. Unit PASS, remote SHA, native qualification and product E2E are different evidence levels.
- Do not close/merge/delete active PRs or historical branches without exact-source semantic harvest, required CI/E2E acceptance and lifecycle absence checks. Do not invoke a second scheduler or runner authority.
- An agent may not claim actual path enforcement from this file or the guard alone: they are checks, **not an OS filesystem sandbox**. Until host-side Work sandbox/ACL admission is independently proved, keep `HOST_FILESYSTEM_ENFORCEMENT=UNVERIFIED` and block any claim of guaranteed containment.

## Current handoff

PR #1173, source a9aaa58684bba398e32970fcb6596a57093815c3: 14 rescued commits, 3 additional Windows Launcher source files and a mode-only cleanup are now published and exact GitHub ref verified. The approved detached WSL recovery worktree is at the predecessor de35de62; preserve it and backups until future qualified handoff. Windows PowerShell/.NET native tests and signed launcher provenance are NOT accepted.

Active operator decision restored Classic Connector Factory and job delivery; the September 30 Cloud-only freeze #1154 is superseded. Pipeline candidate daily budget is 20 new/retry firms plus 50 active sources; a retained backlog is not dropped. The code does not itself prove productive job ingest or UI projection. Avoid introducing a second timer: compare Runtime #399 with the RCC occurrence authority.

Current local test scope: 34 focused JAP Classic unit tests passed; database staging/rollback is not live product E2E.

Source-only documentation/workspace guard must itself be qualified and integrated before being treated as canonical `main` protection.
