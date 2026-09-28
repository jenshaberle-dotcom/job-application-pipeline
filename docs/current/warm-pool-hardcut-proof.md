# Warm-Pool hardcut residual proof

Date: 2026-09-28. Scope: JAP Classic repository candidate, not live host state.
Starting hardcut: `7d10b0b992fce98035b0cc78710547fd71d6ff07`.
Integrated hardcut main: `857534c4983398202714c83387af121d1e92115a`.

## Three scan rounds

1. **Execution identities and physical inventory:** inspect tracked workflows,
   configuration, scripts, tests and documentation for retired routing identities.
   Extend the regression scan from selected directories to every tracked UTF-8
   file, including root contracts, source, Windows assets and archived docs.
2. **References and competing authority:** compare deleted paths with all tracked
   text and inspect release, DRJ, re-entry, planning and ADR authority. Remove
   obsolete publisher claims, workflow registrations, private scheduler authority,
   legacy `.github/triggers/` effect markers and tests demanding deleted transports.
   Preserve product/affinity tests.
3. **Executable validation and recurrence:** collect and execute the entire suite,
   removing the remaining orphan snapshot transport test and unused lease module
   with its tests. Check workflow references and registered workload inventory
   against files that actually exist. Re-run the complete suite and doc checks.

The repository retains two RCC workload targets: exact-PR repository validation and
the reusable assessment cohort, plus one separate cardinality-blind Windows product
release publisher. The publisher runs on
GitHub-hosted `windows-latest` and provides packaging/publication only; it is not runner
allocation authority. Negative guards and historical branch-disposition identifiers are
not runnable allocation authority. Product source-health heartbeats are unrelated to runner
capacity and retain their existing product semantics.

## Validation

- Full pytest: **3812 passed** with repository development requirements installed.
- Documentation references: **PASS**, 407 Markdown files, 865 references,
  zero unresolved references (before this proof document was added).
- Documentation architecture: **PASS**, zero issues.
- Repository CI contract: **PASS** (115 migrations; valid backlog/governance).
- Changed Python files: Ruff **PASS**.
- Whole-repository Ruff: **34 E402 findings**, all in files byte-identical to the
  integrated baseline. Full lint is not represented as green.
- Deleted-path and nonexistent-workflow-reference scans: no residual references.

## Product readiness and external gate

The existing Control Center already contains English Candidate Fit and Top 5
views, including empty-state explanations and missing-evidence fields. The
reusable assessment entrypoint selects jobs generically and invokes the existing
Product authorities. No company/job IDs, score blending or direct rank writes
are introduced by this change.

No database or live workload ran during this scan. Ten complete Fit decisions
and five authoritative Top-5 jobs remain unproven. The later PR-validation
bootstrap restores a repository-test workload through the same RCC demand-only
authority instead of restoring project-owned runner routing.

RCC PR #674 has since merged the generic demand-only adapter. JAP now uses the
same target model instead of preserving a consumer-owned execution profile:

| Boundary | Current authority |
| --- | --- |
| Demand | JAP declares `.rcc/workload-demands.json`; RCC materializes the execution profile |
| Source | exact `source_sha` |
| Dispatch | RCC supplies exact facade label + ephemeral assignment-proof label |
| Assignment | `rcc-assignment-proof-<reservation-id>` |
| Allocation/profile | RCC-only |
| Consumer runner profile | physically absent |

For JAP `linux-base`, RCC must materialize profile
`rcc-demand-jap-linux-base` with hash
`b08aaffd6a5da737b20570a7ed3b5b1bfc3eea11f0efeeb216e5a9d2a030c70e`.

The contract is now structurally compatible, but live acceptance remains unproven.
RCC must still prestage/qualify the demand profile, run the read-only registration
preflight, receive fresh effect authority, register the exact facades and execute
one exact-source workload with deterministic cleanup. JAP must not restore a
runner contract, consumer runner profile, broad labels, fixed member choice or a
second scheduler while those gates are completed.

JAP Classic's explicit local assessment action remains separate from runner
authority: it owns no allocation, scheduler or dispatch path and validates the
cohort report before accepting its result. Product release publication is likewise
separate from workload allocation: the protected hosted Windows publisher builds and
publishes immutable exact-source assets when `windows/JAP.ControlCenter.Desktop/VERSION`
changes. Through the 2026-09-29 demo it must not be deleted or migrated; any post-demo
RCC publication replacement must be proven before removing this update channel.

## Product acceptance follow-up

The assessment report now counts complete/passed/rankable jobs only within its
selected current Employer-Origin cohort, rejects duplicate selected identities,
and rejects duplicate Top-5 identities or non-contiguous ranks. A failed nested
authority also fails the read-only plan instead of allowing the workflow to apply.
One Product payload supplies the postflight projections. The Control Center now has
an explicit local operator action that invokes this same generic cohort with fixed
10/5/15 targets and refuses report drift such as provider use, direct rank/Top-5
writes, numeric Candidate Fit or a combined Fit/Affinity score.

Targeted validation: 19 tests passed across cohort behavior, workflow contract and
repository-wide retired-authority guards. The original 3812-test full-suite result
above belongs to the residual-proof baseline; no live database or runner effects
were performed for this follow-up.
