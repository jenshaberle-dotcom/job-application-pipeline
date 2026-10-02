# JAP Classic engineering re-entry

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
