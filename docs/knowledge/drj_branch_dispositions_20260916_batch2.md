# DRJ branch disposition ledger — 2026-09-16 batch 2

Status: proposed project-side semantic evidence for DRJ branch hygiene  
Repository: `jenshaberle-dotcom/job-application-pipeline` (`1230805345`)  
Scope: exactly three additional SHA-bound terminal records, extending `DRJ-BRANCH-DISPOSITIONS.json` from 14 to 17 records.

## Safety boundary

This ledger provides semantic disposition evidence only. It grants neither effect authority nor delete authority. Default-branch, persistent-ref, open-PR, local-worktree, active-workflow, exact-SHA, API-budget, runtime-veto, standing-authority and post-effect reconciliation gates remain authoritative.

Every record below is bound to the exact current branch head observed on 2026-09-16. Any SHA drift invalidates the record and must fail closed to preserve/review.

## Additional terminal records

### `agent/warm-hosted-fallback-jobapp-001a`

Exact head: `62dd3754fadd739a6f8124fa0f8a3cccf2e81bed`  
Disposition: `SUPERSEDED / CANONICALIZED`

PR #701 explicitly states that this stale-base fallback implementation was superseded after the independent DOC-001L main repair and that its implementation was preserved unchanged by reconstruction as `agent/warm-hosted-fallback-jobapp-001b`. PR #703 is that reconstructed implementation and merged it to default `main` as merge commit `6bcfe9a0c7c45278bccb54cb8c9621020910fa98`. The old `001a` head therefore contains no independently authoritative product capability.

### `refs/heads/docs/acq-runtime-api-strategy-reentry`

Exact head: `7e9d08a2ce2bda0e414f6125a460931eaf287255`  
Disposition: `SUPERSEDED / CANONICALIZED`

PR #647 comment `5409560425` explicitly marks the branch stale and superseded by #653, states that repository/runtime truth had advanced, and directs that the stale re-entry branch must not be merged. PR #653 explicitly says it supersedes #647's stale re-entry state, refreshes ACQ-RUNTIME-001 documentation and REENTRY-001A from the newer evidence, and was merged to default `main` as `657d4c84a03a0327d152eb5c158a005166b4bfbb`.

### `feature/runtime-runner-selector-hardening`

Exact head: `1833eafadabd3b8f6dac80de14614929a099d10f`  
Disposition: `DEPRECATED / REJECTED`

PR #644 is explicit terminal project evidence: it was closed without merge after runtime diagnosis because the selector was not the root cause. The runner was correctly repository-scoped to the private runtime companion, the proof was moved there, and the PR explicitly states that no public runner-selector weakening should be merged. The branch's unique change is therefore intentionally rejected rather than harvested into JAP.

## Still preserve/review

The following known historical refs remain outside machine terminal disposition because exact-head semantic evidence is still insufficient:

- `agent/676-deterministic-connector-builder`: current head materially extends beyond the historical harvest evidence;
- `agent/p1-connector-delivery-audit`: no sufficiently explicit exact-head terminal handoff established;
- `agent/f2-acceptance-cohort` and `agent/f2-operator-cold-e2e`: no durable project-side terminal evidence established;
- `agent/rcc-step1-wsl-inventory-001a`: one-time/read-only intent alone is insufficient;
- `agent/winapp-020-prebuilt-frontend-startup`: no exact terminal successor/harvest proof established for the branch head;
- `rcc-workload-ready-jap-canary` and `tmp/jap-lockgen-final`: temporary carrier intent alone is insufficient.

No branch is made retireable from age, naming, inactivity, branch pressure or similarity alone.
