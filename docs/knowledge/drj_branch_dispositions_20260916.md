# DRJ branch disposition ledger — 2026-09-16 batch 1

Status: proposed project-side semantic evidence for DRJ branch hygiene  
Repository: `jenshaberle-dotcom/job-application-pipeline` (`1230805345`)  
Scope: exactly the 14 records in root `DRJ-BRANCH-DISPOSITIONS.json`

## Safety boundary

This ledger and `DRJ-BRANCH-DISPOSITIONS.json` provide **semantic disposition evidence only**. They do not grant deletion authority and do not bypass default-branch, persistent-ref, open-PR, local-worktree, active-workflow, exact-SHA, API-budget, runtime-veto, standing-authority or post-effect reconciliation gates.

Every record is bound to the exact branch head observed on 2026-09-16. If a branch moves, DRJ must treat the record as stale and preserve it. Branches omitted from batch 1 remain `HARVEST_PENDING` / preserve-review.

## Terminal records

### `agent/630-workday-cxs-acquisition`

Exact head: `c6dc7ddf8ccfb1c90ae1c32d578afed669759ba8`  
Disposition: `SUPERSEDED / CANONICALIZED`

`docs/knowledge/branch_salvage_704.md` explicitly records that the old branch-only V4 Workday integration is semantically subsumed by the current dedicated Workday acquisition architecture, that current main preserves and strengthens the same authorized-root → CXS inventory → same-board detail → unchanged genuine-job-proof contract, and that the old direct V4 integration must not be revived. The current acquisition migration checkpoint independently preserves the historical Workday precedent and recovered contract.

### `agent/676-external-deterministic-salvage`

Exact head: `e4a7b980a19fdcf1f0b312f9d3ae2af904012501`  
Disposition: `RETIRE / HARVESTED`

`docs/knowledge/branch_salvage_704.md` explicitly records an ancestry-free harvest onto current-main ancestry in commit `b06827bae362893f5a0be20aa8ba39e9afd78bb0`. The five harvested files named by that record are the branch's current semantic delta: the V6 audit, provider public-feed capability, planning record and their tests. Historical branch ancestry is intentionally not required after that harvest.

### `agent/707-private-candidate-fact-approval`

Exact head: `893ec176cb4acbd8542f0f0de348567e9561c42b`  
Disposition: `SUPERSEDED / CANONICALIZED`

PR #720 explicitly says it is superseded by ancestry-clean reconstruction #721, that the exact capability was preserved and re-qualified on fresh main, and that no value remains uniquely authoritative on the stale branch. PR #721 merged that reconstructed capability as merge commit `cebf85a5645e3c5e2a280255dfadbf2a5e16cfef`.

### `agent/707-private-candidate-fact-approval-refresh`

Exact head: `6a5eec28b01c7ff8113f762392dca4f577a1c4ac`  
Disposition: `SUPERSEDED / CANONICALIZED`

PR #722 describes this branch as a refresh of the same already-green #720 Candidate Fact approval slice. PR #721 had already reconstructed and merged that capability on current main. Fresh snapshot verification on 2026-09-16 confirms the branch test file `tests/test_approve_private_candidate_fact_profile.py` is byte-identical to main; the implementation file differs only by an explanatory comment immediately before the same strict canonical re-parse. There is no distinct product capability to retain from this refresh branch.

### `agent/f4a-profile-fit-coverage`

Exact head: `36fc1ce891b28a30db0085c86a14051d9f7c6b01`  
Disposition: `SUPERSEDED / REJECTED`

PR #867 was closed unmerged before implementation. Owner comment `5648479625` explicitly states that canonical main advanced, F4A continues on #868 from fresh exact main, and no product implementation from #867 is carried independently. PR #868 then merged the F4A implementation to main.

### `agent/origin-entity-locale-and-brand-aliases`

Exact head: `2d6be950b4b703c9332cf609758bf62551e5184c`  
Disposition: `DEPRECATED / REJECTED`

PR #322 owner comment `5175702498` records the finite three-attempt error process and explicitly declares the combined implementation abandoned. The proven entity/locale protection was to be re-extracted cleanly, while unsafe generic market-acronym inference was rejected. The old combined branch must not be revived as canonical implementation.

### `agent/origin-evidence-main-integration-001`

Exact head: `2c60bea92b51c03f28b5a6a9c28ecb09f4d3d87e`  
Disposition: `RETIRE / CANONICALIZED`

PR #279 existed solely to integrate then-current main into the origin-evidence line without rewriting reviewed history. It merged into the non-default PR #277 line, and its merge result became #277's final head `8a3e613b4386fd51697d82e9ca3b0c95ba4bc533`. PR #277 subsequently merged to default `main`. The integration branch therefore has no independent surviving product line.

### `agent/origin-secret-names-001`

Exact head: `cc7cab411460f2b02672d1a44743411fd1f2d5e4`  
Disposition: `SUPERSEDED / CANONICALIZED`

PR #275 owner comment `5141887738` explicitly states that #278 reapplies the useful credential-contract hardening on current runtime/recovery main and that #275 is intentionally not merged because it predates that foundation. PR #278 explicitly identifies itself as the replacement and merged to main.

### `agent/p1-full-connector-inventory-audit`

Exact head: `50ecf6326565e34a915c9a50cec95c25ede2a023`  
Disposition: `SUPERSEDED / REJECTED`

PR #837 is explicit diagnostic evidence. Its body states that the first full-connector audit answered a narrower question than the P1 blocker, that it is superseded by a fresh exact-main audit, and that the PR is intentionally not merged. The branch implementation is therefore not retained as product code.

### `agent/p1-generic-origin-z-baseline`

Exact head: `0d5c81aa7505d035b138d3cfc4ca7176ad646877`  
Disposition: `DEPRECATED / REJECTED`

PR #845 records a one-time read-only baseline, including its observed `y=23, z=0` result and zero-write/network boundaries, and explicitly says the PR was closed unmerged as intended. The durable result is preserved in the PR evidence; the one-time carrier branch is not product implementation.

### `agent/p1-origin-initial-proof-revalidation`

Exact head: `df9160ea0962163078c0beb955cf4eb1167992be`  
Disposition: `SUPERSEDED / REJECTED`

PR #839 explicitly states that the diagnostic went too far into vocabulary/relevance before resolving the product supply gap, defines the superseding P1 acquisition-promotion sequence, and states that no code from the diagnostic PR is merged.

### `agent/p1-promote-proven-origin-connectors`

Exact head: `851d3983a9b048229e16a6b4bdd8d5e71dbdbff7`  
Disposition: `SUPERSEDED / REJECTED`

PR #840 explicitly records the later operator architecture decision: the generic deterministic layer model is the sole connector discovery/validation authority; V6/demo/historical admission truth must not be used for activation; no registration/activation/Bronze mutation from the branch is retained.

### `agent/v41-manual-hardening`

Exact head: `9a0eaa384ece495c05c171da57c3f7d18fef9a5b`  
Disposition: `DEPRECATED / REJECTED`

`docs/knowledge/branch_salvage_704.md` explicitly records that the old PR #663 regression invariant is stale under later qualified evidence. Current main has the stronger surviving boundary, and the old #663 test must not be restored.

### `hotfix/product-v1-view-type-stability`

Exact head: `235dfe955e28dfd4e7b4fcd5e0bb7db1a1fc7740`  
Disposition: `RETIRE / HARVESTED`

`docs/knowledge/branch_salvage_704.md` explicitly records that the exact useful two-line PostgreSQL view type-stability delta was harvested into ancestry-free migration commit `b06827bae362893f5a0be20aa8ba39e9afd78bb0`: `overall_quality_score` is explicitly `NUMERIC(6, 2)` and recursive `product_rank` is explicitly `BIGINT`.

## Explicitly not resolved by batch 1

The following known historical refs remain preserve/review because current exact-head evidence is not yet sufficient:

- `agent/676-deterministic-connector-builder`: current head has 36 commits unique to main comparison and materially extends beyond the historical #678/#682 harvest evidence;
- `agent/p1-connector-delivery-audit`: diagnostic history exists, but no sufficiently explicit exact-head terminal handoff has yet been established;
- `agent/f2-acceptance-cohort` and `agent/f2-operator-cold-e2e`: no durable project-side terminal evidence located;
- `agent/rcc-step1-wsl-inventory-001a`: one-time/read-only naming and commit intent alone are not terminal semantic evidence;
- `agent/warm-hosted-fallback-jobapp-001a`, `agent/winapp-020-prebuilt-frontend-startup`, `refs/heads/docs/acq-runtime-api-strategy-reentry`, `feature/runtime-runner-selector-hardening`, `rcc-workload-ready-jap-canary`, `tmp/jap-lockgen-final`: require separate exact-head successor/harvest/rejection proof.

This omission is intentional. No branch is made retireable from age, naming, apparent inactivity, branch pressure, or similarity alone.
