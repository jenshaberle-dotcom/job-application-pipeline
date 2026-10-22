# JAP Classic engineering re-entry

## Current source and recovery checkpoint — 2026-10-22 (candidate, not main acceptance)

The dated October 2 material below is **historical**, not the live current head. Repository `main` remains `819e0df0a9ea8c92866dfdb2ac4f17acdee0d10f` as of the documented checkpoint. Current Classic operator direction is **active Connector Factory + job delivery**, not the superseded September 30 Cloud-only feature-freeze (#1154).

- Active delivery [PR #1173](https://github.com/jenshaberle-dotcom/job-application-pipeline/pull/1173), exact recovered head `442ab273cb913d81c0cf196e6ed0faead8441352`: 14 local commits recovered and remote SHA verified.
- New native market occurrence sources are bounded (20 new/retry candidates plus 50 active sources per run) and retain backlog/uncertain-stage receipts. Source-only unit tests 34/34 PASS; this **does not** qualify production sensor → Origin → Bronze → Silver → Product/UI E2E or release/adoption.
- The three Windows Launcher source files were separately salvaged and remain untracked in the approved local recovery worktree, not included in #1173 yet. There is **no** GitHub replacement for these local bytes until qualified/committed.
- RCC candidate [#753](https://github.com/jenshaberle-dotcom/Runner-Control-Center---RCC/pull/753) head `49ccac9d0c3612ec581dd208ba05e87b906ce0f9`; private Runtime due-work candidate [#399](https://github.com/jenshaberle-dotcom/job-pipeline-runtime/pull/399) must not introduce a competing scheduler.
- Existing GitHub/branch harvest is tracked by [#1172](https://github.com/jenshaberle-dotcom/job-application-pipeline/issues/1172), [#704](https://github.com/jenshaberle-dotcom/job-application-pipeline/issues/704), with the fully paginated branch census in [`BRANCH-CENSUS-20261022.json`](BRANCH-CENSUS-20261022.json).
- Future Work Cloud source changes use authenticated GitHub commits only; Work Local requires registered WSL worktrees and real host containment admission. See `AGENTS.md` and [the Work continuation](WORKCHAT-REENTRY-20261022.md). No other local checkout gains project authority.

**Do not silently reconcile the 2026-10-02 version/model statements below to current installed truth.** Installed desktop, live DB, release and native RCC host state remain independently unverified until fresh evidence.

Inspected: 2026-10-02. Repository ID: `1230805345`.
Baseline before this documentation hardcut: `effe8cc7aafcc2e31a9c471e1eaf678f22b6d3f1`.
This is a dated inspection record, not a lock on a moving `main`.

## Established repository facts

- React Control Center and .NET 8/WebView2 desktop host are present.
- Desktop version file is `1.2.6`; root `VERSION` is `1.0.61` and is not desktop identity.
- GitHub published desktop `jap-winapp-product-v1.2.6` on 2026-09-29.
- All four workflow targets use exact RCC assignment. Windows packaging is now an RCC
  workload; old statements about hosted publication or no publisher are obsolete.
- Consumer demand declares `linux-base` and `windows-release` capabilities without runner counts.
- Freeze-II generic activation remains withheld in its current authority file.
- Current drafting adapter defaults to `gpt-5.6-sol`. PR #1160 proposes a GPT-6.1 change;
  it was open at inspection and is not implementation truth on this baseline.

## Evidence still required

This inspection does not establish installed version, live database/Top-5 state, successful
RCC production execution, physical legacy-runner retirement or Cloud parity. Obtain exact-source
run/job evidence and current runtime identity before making those claims.

The 10→5 cohort is reusable product validation. Its result must meet normal Fit, hard-filter
and ranking contracts; publishing a version does not prove cohort acceptance.

## Continue safely

1. Verify live repository ID, `main`, working branch and open PR state.
2. Inspect current code and workload demand; use [RCC execution](ci-max-execution.md).
3. Check completed evidence on the exact current head before rerunning work.
4. For product effects, inspect DB/audit state and applicable approval boundaries first.
5. Continue from [roadmap](../planning/active/roadmap.md); do not replay old demo, acquisition
   or MCP-freeze sequences from historical notes.
6. Validate current head, review the concrete diff and merge only after required checks pass.

Pending proposals may contain reusable work. Open PRs #1152, #1155, #1159 and #1160 were
visible at inspection; refresh GitHub before treating their state or contents as current.
