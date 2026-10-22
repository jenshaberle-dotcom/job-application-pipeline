# JAP Classic — Workchat re-entry and harvest ledger (22 October 2026)

Status: **dated engineering snapshot; NOT a product, release, host or merge acceptance**.
Canonical ref and repository identity are defined by `PROJECT-REENTRY.json` on `main`; fetch current GitHub heads for any continuation. This document is an additive locator, never a replacement for historical records.

## Current slices / exact source evidence

PR #1173, source 442ab273cb913d81c0cf196e6ed0faead8441352; 14 October 21 local commits have been recovered and pushed. Three untracked Launcher source files remain in the WSL recovery worktree.

## Risks, evidence and constraints

Active operator decision restored Classic Connector Factory and job delivery; the September 30 Cloud-only freeze #1154 is superseded. Pipeline candidate daily budget is 20 new/retry firms plus 50 active sources; a retained backlog is not dropped. The code does not itself prove productive job ingest or UI projection. Avoid introducing a second timer: compare Runtime #399 with the RCC occurrence authority.

34 focused JAP Classic unit tests passed; database staging/rollback is not live product E2E.

Three-project harvest ledger: RCC issue #748, JAP Classic issue #1172 (Factory #1166), JPR issue #403. Legacy PRs closed **without merge** retain branch and exact source history; code/host lifecycle retirement is a separate acceptance gate.

## Next Work-mode E2E sequence

1. Read `AGENTS.md`, native reentry and workspace contract; establish **actual local path and platform** before any write.
2. Run the checked-in `tools/workchat_workspace_gate.py --phase before-edit` from the declared registered WSL feature worktree. Unqualified or stale canonical checkout blocks mutation.
3. Read fresh PR head, source diff, retained receipts, uncertain effects and exact GitHub results. Never infer completion from a unit test or a previous chat.
4. Continue the active slice, preserving one controller, one authoritative occurrence scheduler and the already-established receipt/fence lineage. Classify parallel legacy candidates without executing them.
5. Validate narrowed tests, native workflows, host effects and product-visible results separately. Do not treat a source commit as installed or accepted.
6. Commit and push each coherent unit without force; verify remote exact SHA. Run the same gate `--phase after-push`, record remaining blockers in existing PR/issue; never leave unpushed results trapped in a Work workspace.

## Outstanding Work containment qualification

- The repository gate refuses writes **when invoked** outside WSL declared paths; `AGENTS.md` supplies agent admission guidance.
- Neither can sandbox arbitrary host filesystem writes from a Work process that ignores them. Host Work must be configured to expose only approved WSL worktrees as editable and an OS-level isolation/ACL test must prove negative access to `Documents/Codex` and other unapproved paths.
- Until that negative test and loss-of-session remote persistence test pass, classify `WORK_HOST_ENFORCEMENT=UNVERIFIED`; operator rescue is not guaranteed unnecessary.
- Do not alter running RCC/JAP/JPR services or installed runner state merely to qualify documentation.
