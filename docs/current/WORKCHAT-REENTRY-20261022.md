# JAP Classic — Workchat re-entry and harvest ledger (22 October 2026)

Status: **dated engineering snapshot; NOT a product, release, host or merge acceptance**.
Canonical ref and repository identity are defined by `PROJECT-REENTRY.json` on `main`; fetch current GitHub heads for any continuation. This document is an additive locator, never a replacement for historical records.

## Current slices / exact source evidence

PR #1173, source 442ab273cb913d81c0cf196e6ed0faead8441352; 14 October 21 local commits have been recovered and pushed. Three untracked Launcher source files remain in the WSL recovery worktree.

## Risks, evidence and constraints

Active operator decision restored Classic Connector Factory and job delivery; the September 30 Cloud-only freeze #1154 is superseded. Pipeline candidate daily budget is 20 new/retry firms plus 50 active sources; a retained backlog is not dropped. The code does not itself prove productive job ingest or UI projection. Avoid introducing a second timer: compare Runtime #399 with the RCC occurrence authority.

34 focused JAP Classic unit tests passed; database staging/rollback is not live product E2E.

Three-project harvest ledger: RCC issue #748, JAP Classic issue #1172 (Factory #1166), JPR issue #403. Legacy PRs closed **without merge** retain branch and exact source history; code/host lifecycle retirement is a separate acceptance gate.

## Operational mode decision — 22 October 2026

**Cloud-first for all source-only work.** A new Work Cloud chat should connect to the existing GitHub repository/PR only and have *no Windows local folder grant*. Every finished source slice is committed via authenticated GitHub connector and independently verified against the exact remote ref. Cloud scratch files are ephemeral; no Windows host clone is needed or authorized. GitHub commit visibility is required **before** token-exhaustion termination.

**Work Local is an exception for real host proof.** The desktop operator must attach only the approved registered WSL worktree. Work Local must fail a negative Windows `Documents/Codex` write test under the *same execution identity* used for the real task and prove a successful in-root write. Work's per-folder approval and an `AGENTS.md` prompt are **insufficient evidence of OS-level negative enforcement**. Workspace/Agent Security requirements may be available only to workspace admins/eligible rollouts; absence is a block, not implicit approval.

No source-authoritative copy may persist outside the allowed project roots; old `Documents/Codex` checkout material is **PRESERVE_FOR_FORENSICS**, not an editable fallback. Work tasks on web/mobile have no direct host filesystem; Work Cloud and Work Local are different environments. Official guidance: https://help.openai.com/en/articles/20001275-chatgpt-work-and-codex and https://help.openai.com/en/articles/20001548-agent-security-and-local-work-sync-in-chatgpt.

## Next Work-mode E2E sequence

1. Read `AGENTS.md`, native reentry and workspace contract; choose GitHub-only Cloud for source tasks by default. Establish actual local path/platform only when local host E2E is essential.
2. For Work Cloud, authorize GitHub-only source mutation using fresh expected PR/ref SHA and the project restart/authority gate; do not mount a local directory. For Work Local, run the checked-in `tools/workchat_workspace_gate.py --phase before-edit` from the registered WSL feature worktree. Unqualified or stale canonical checkout blocks local mutation.
3. Read fresh PR head, source diff, retained receipts, uncertain effects and exact GitHub results. Never infer completion from a unit test or a previous chat.
4. Continue the active slice, preserving one controller, one authoritative occurrence scheduler and the already-established receipt/fence lineage. Classify parallel legacy candidates without executing them.
5. Validate narrowed tests, native workflows, host effects and product-visible results separately. Do not treat a source commit as installed or accepted.
6. Commit each coherent unit via GitHub expected-head lease or local fast-forward push; independently read back exact remote SHA. For Work Local also run the checked-in gate `--phase after-push`. Record remaining blockers in existing PR/issue; never leave unpushed results trapped in a Work workspace.

## Cross-project host admission test — source prepared, host evidence missing

The single cross-repository inventory and opt-in containment probe is maintained **only** in [RCC #756](https://github.com/jenshaberle-dotcom/Runner-Control-Center---RCC/pull/756): `tools/linux/Inspect-WorkchatHost.py`. Do not fork it into JPR or JAP and do not add a monitoring daemon.

**Safe read-only WSL inventory:** `python3 -B tools/linux/Inspect-WorkchatHost.py --mode inventory` from the qualified RCC source checkout. The report observes origin, current HEAD/branch, dirtiness, live `origin/main` and registered worktrees for all three repositories; it does not promote a restart gate to PASS.

**Only inside a real Work Local WSL execution session**, explicitly run `python3 -B tools/linux/Inspect-WorkchatHost.py --mode containment --allowed-worktree "<actual registered WSL worktree root>" --denied-windows-codex "/mnt/c/Users/<WindowsUser>/Documents/Codex"`. The containment mode creates and removes only a unique zero-byte test sentinel at each designated location. It reports `PASS` only when the in-root write succeeds and an outside write fails with a real OS permission denial. A missing or inaccessible directory is `NOT_PROVEN`, not PASS; successful outside write is `FAIL_OUTSIDE_WRITE_POSSIBLE`. Do not run this test in an unrelated operator shell and claim it describes Work's own permissions.

The checked-in Worktree gate and host-probe scripts have **source-level isolated regression evidence**: 5/5 for the shared guard in all three PRs, plus 5/5 for the RCC host probe, each with byte-for-byte Git blob SHA confirmation. These are not native WSL/Windows/Work isolation evidence; actual host security remains **UNVERIFIED**.

## Native GitHub delete-on-merge setting — pending administrative execution

The existing portfolio policy requires `delete_branch_on_merge=true` independently on each of the three repositories. Current API readback on 22 October was `false`. The sole bounded helper, [`RCC tools/linux/Set-PortfolioDeleteOnMerge.sh`](https://github.com/jenshaberle-dotcom/Runner-Control-Center---RCC/blob/governance/workchat-wsl-reentry-20261022/tools/linux/Set-PortfolioDeleteOnMerge.sh), accepts `--inspect` (GET only) or explicit `--apply` (PATCH only these three repo settings, then exact readback). Syntax qualified in an isolated shell; **admin application NOT executed** by the current GitHub connector. It does not merge, delete any branch, or prove native automatic post-merge absence. Do not report lifecycle complete before a normal qualified PR merge actually demonstrates deletion and absence.

## Operator host preflight and repository setting — 22 October 2026

**Live GitHub readback:** `delete_branch_on_merge=true` for RCC, JAP Classic and JPR; this resolves the setting itself, **not** the first real qualified post-merge source-ref absence proof.

A read-only real-WSL inventory was executed from exact RCC source blob `3f79524a32bdacf24a562ef86a5a23554a36cee2` and returned `host_reentry_pass=false`. All three canonical checkouts are clean and have exact GitHub origins, but **RCC canonical main** is `a29a7c9b6d3fccc0f44e0067dc5802573785f8cd`, remote `2355858961c145788b6a01e97120fe8e4f7d9749` (GitHub compare: 145 strictly remote-only commits); **JAP Classic main** is `effe8cc7aafcc2e31a9c471e1eaf678f22b6d3f1`, remote `819e0df0a9ea8c92866dfdb2ac4f17acdee0d10f` (63 strictly remote-only commits); **JPR main** is `f477e2316448cb42812f9e87a1786fca1ff7b4af` on both local and remote. There are many registered old RCC/JAP worktrees, including **RECOVERY_SOURCE_PRESERVE** worktrees and a separate JAP Control Center installed runtime Git worktree outside the declared engineering root. Never prune that runtime worktree as if it were unowned source debt.

**Next bounded host step:** execute the current source-only `RCC tools/linux/Classify-PortfolioWorktrees.py --summary` from [RCC governance PR #756](https://github.com/jenshaberle-dotcom/Runner-Control-Center---RCC/pull/756), pinned by exact Git blob SHA. It classifies every locally registered worktree's branch/HEAD, dirty state, unique history relative to the **stale** local main, and limited process cwd evidence. This inventory authorizes **no deletion**, `git pull`, reinstall, service restart, `worktree prune` or retry. Source and local WSL test are separately gated.

**Do not fast-forward the stale canonical RCC/JAP main checkouts before checking which running services and installed product files depend on them.** The two main histories are fast-forward related according to the live GitHub comparison, but that is not a host-impact proof. Work Local filesystem containment has **not** been proved under the real Work execution identity. Remainder: host worktree/branch harvest, allowed-path negative write test, exact PR source CI, and post-merge absence evidence.

## Outstanding Work containment qualification

- The repository gate refuses writes **when invoked** outside WSL declared paths; `AGENTS.md` supplies agent admission guidance.
- Neither can sandbox arbitrary host filesystem writes from a Work process that ignores them. Host Work must be configured to expose only approved WSL worktrees as editable and an OS-level isolation/ACL test must prove negative access to `Documents/Codex` and other unapproved paths.
- Until that negative test and loss-of-session remote persistence test pass, classify `WORK_HOST_ENFORCEMENT=UNVERIFIED`; operator rescue is not guaranteed unnecessary.
- Work Desktop must be launched with **only the explicitly needed local project folder** granted; the GitHub repository checkout must then resolve to the approved WSL root. A Windows Codex shadow directory is not an acceptable checkout even if accessible.
- If the account/workspace supports OpenAI **Agent Security > Local environment**, configure *requirements* for filesystem permissions/sandboxing (not merely defaults). Work Local and Work Cloud are separate execution environments; never infer that a Codex Cloud policy constrains Work Local. This capability is eligibility-dependent and **has not been observed or configured on this host**.
- Official product guidance: https://help.openai.com/en/articles/20001275-chatgpt-work-and-codex and https://help.openai.com/en/articles/20001548-agent-security-and-local-work-sync-in-chatgpt
- Do not alter running RCC/JAP/JPR services or installed runner state merely to qualify documentation.
