# JAP Classic re-entry

Updated for the 1.2.2 runner hard cut.

## Current product target

JAP Classic 1.2.2 is the current live-inspection/demo candidate. Publishing it does not itself prove the 10-to-5 Product target.

Required product proof before claiming the 1.2.2 Product target complete:

1. all seven market sensors visible in Sources with verified discovery evidence;
2. at least 10 current Employer-Origin jobs with complete Candidate Fit decisions;
3. at least 5 Fit-passed jobs satisfying normal hard-filter/ranking authority;
4. authoritative Top 5 contains exactly 5 jobs;
5. no job IDs, employers, direct rank writes or demo-only promotion bypasses.

The reusable RCC Product workload target is `.github/workflows/product-v1-assessment-cohort.yml`.
The separate `.github/workflows/jap-windows-desktop-host-release.yml` is product packaging/publication infrastructure only; it runs on GitHub-hosted `windows-latest` and owns no Warm-Pool allocation, facade or physical-runner authority.

Canonical Product 10→5 implementation:

```text
run_product_v1_assessment_cohort
→ select exactly 10 current Employer-Origin jobs
→ run_product_v1_rankable_refill_campaign
   → generic scout / exact-detail refresh
   → run_product_v1_rankable_refill_apply
      → Candidate-Fact-backed capability review
      → run_product_v1_hard_filter_evidence_close
      → canonical ranking-score review
→ verify 10 complete Candidate Fit decisions
→ verify at least 5 Fit-passed + rankable jobs
→ verify exact Top 5 is a subset of the selected 10
```

Candidate geography/work-model preferences come first from approved private
`operator_preference` Candidate Facts. If none exist, the tracked approved
`config/product_v1_candidate_fit_policy.json` supplies the reusable product
boundary (regional anchor/commute plus country-wide remote).

The old `run_demo_001_rankable_refill_*` names are compatibility entrypoints only.
The old job-specific DEMO-001 hard-filter closer is physically removed. Demo
entrypoints must not regain Product logic or become dependencies of the canonical chain.

## Runner authority hard cut

The repository no longer owns workload runner allocation.

Canonical chain:

```text
JAP workload demand
→ RCC
→ RCC admission/reservation
→ RCC-selected Warm-Pool member
→ exact repository facade
→ ephemeral assignment label
→ exact-source JAP workload
→ RCC verification/cleanup/release
```

Physically removed from JAP:

- project-owned direct self-hosted assignment workflows;
- broad runtime labels and their freeze/fallback guards;
- heartbeat-based routing;
- fixed Warm-Pool member selection;
- repository-owned hosted/warm route selection;
- retired Blue-runner workflow archive;
- legacy workflow trigger authority files under `.github/triggers/`;
- project-owned runner allocation contract;
- local Windows scheduled-pipeline runner path;
- old workflow-specific regression tests that could restore those authorities.

The assessment-cohort workflow is the **only RCC workload target**. JAP now declares
its execution need through `.rcc/workload-demands.json`; RCC owns profile
materialization, allocation, facade selection and capability provisioning. The consumer-owned runner-profile tree is physically absent.

The Windows product release publisher is intentionally outside that workload topology: it only builds exact-source immutable desktop/runtime assets and publishes the GitHub Release. It must remain cardinality-blind and must never acquire self-hosted, facade or physical-member selection.

Current demand mapping:

```text
product-v1-assessment-cohort.yml
→ linux-base
→ platform linux-wsl
→ runtime python-project
→ RCC materializes rcc-demand-jap-linux-base
→ expected materialized profile hash b08aaffd6a5da737b20570a7ed3b5b1bfc3eea11f0efeeb216e5a9d2a030c70e
```

## Current next gate

The three residual scans are complete on the residual-proof candidate; see
`docs/current/warm-pool-hardcut-proof.md` for scope, fixes and validation.
The runner hardcut is merged on `main` as `857534c4983398202714c83387af121d1e92115a`;
the Candidate-Fit/Top-5 projection clarification is merged as
`717ae8654c3cff6641fdbcb1567935276cf55608`. This is repository proof, not RCC
live execution acceptance.

The repository hardcut itself is independent from runtime acceptance; keeping stale
runner authority on `main` is not a valid substitute for external execution proof.
RCC PR #674 has now merged the generic `RCC_WORKLOAD_DEMAND_V2 + EXACT_SOURCE_V1`
adapter required by JAP. JAP's RCC workload consumes only
`source_sha + rcc_facade_label + rcc_assignment_label`; it does not choose a
physical member or persistent facade. The product release publisher is not an RCC workload and does not consume these routing inputs.

No RCC execution of the JAP assessment workload has been proven yet. The remaining
RCC operational gates are profile prestage/qualification, read-only five-member
registration preflight, fresh operator registration authority, facade registration,
and then one exact-source production dispatch with cleanup proof.

JAP Classic may run the same generic assessment cohort locally through the explicit
Control Center operator action `/api/v1/product-v1/assessment-cohort`. That path
selects no runner, creates no scheduler and restores no repository allocation
authority; it delegates only to the existing Candidate Fit, hard-filter and ranking
authorities. Its child report must prove apply mode, exact 10/5/10 targets, zero
provider requests, zero direct rank/Top-5 writes and no combined score before the
Control Center accepts the result.

The cohort acceptance now counts only selected, current Employer-Origin jobs.
Failed Fit decisions count as evaluated, never passed. Duplicate Top-5 identities,
non-contiguous ranks and failed plan authorities fail closed. These are local
regression checks, not evidence that the live database meets the 10-to-5 target.

Product sequence:

1. from the installed/local Classic Control Center, explicitly run **Evaluate current jobs**
   (or the same generic cohort CLI) against exact JAP main;
2. repair reusable evidence blockers while retaining all Fit/hard-filter gates until
   the validated report proves 10 complete Fit decisions, at least 5 Fit-passed/rankable
   jobs and exactly 5 authoritative Top-5 jobs;
3. verify the English Candidate Fit and Top 5 surfaces against that live Product truth;
4. complete RCC demand-v2 prestage/registration and one exact-source cohort proof for
   future automated/remote runs; keep the restored cardinality-blind hosted Windows
   product publisher intact through the 2026-09-29 demo. Any later migration of publication
   into RCC must prove the replacement before this update channel is removed;
5. install and run the operator smoke for Sources, All Jobs, Candidate Fit and Top 5.

Do not claim populated Top 5 or Product-target completion until the live assessment report has
`target_met=true`. The 1.2.2 package may be published beforehand for exact-product live inspection.
