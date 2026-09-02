# Branch Salvage 704 — Post-Migration Value Ledger

Status: active preservation record
Owner: issue #704
Repository: `jenshaberle-dotcom/job-application-pipeline`
Repository ID: `1230805345`

## Purpose

Preserve semantic project value before historical branch/worktree retirement under the current hygiene rules.

This document is **not cleanup authority**. It records what was harvested, what is intentionally superseded, and which invariants remain useful. Branch age, naming, merge status, or repository pressure never establish delete authority.

## 2026-09-02 remote/host audit

The canonical WSL preflight observed:

- clean canonical checkout on `main`;
- `origin/main = 6bcfe9a0c7c45278bccb54cb8c9621020910fa98`;
- 296 remote refs including `main`;
- 1 open PR-protected ref;
- 2 branch-only refs with unique patch IDs;
- 9 closed-unmerged PR refs requiring semantic review;
- 55 merged-PR refs with patch-ID deltas caused by historical/squash/divergent ancestry and therefore requiring successor/provenance classification rather than blind deletion;
- 227 refs with no unique patch against current main;
- persistent `feature/ml-learning-foundation` remains explicit PRESERVE.

No reset, clean, checkout, branch deletion, worktree removal, or remote-ref mutation was performed by the audit.

## Harvested onto current-main ancestry

Commit `b06827bae362893f5a0be20aa8ba39e9afd78bb0` was reconstructed with **exactly one parent**, `main@6bcfe9a0c7c45278bccb54cb8c9621020910fa98`.

It preserves the following qualified value without importing historical branch ancestry:

### ACQ-676 V6 provider public-feed capability

Source: open PR #695 / `agent/676-external-deterministic-salvage`.

Harvested files:

- `docs/planning/active/acq676_external_deterministic_salvage.md`
- `scripts/run_deterministic_connector_builder_layer_audit_v6.py`
- `src/connectors/employer_origin_provider_public_feed.py`
- `tests/test_deterministic_connector_builder_layer_audit_v6.py`
- `tests/test_employer_origin_provider_public_feed.py`

Durable capability rules:

1. Prefer reusable provider-family capabilities over employer-specific rescue code.
2. Provider recognition alone grants no employer, tenant, board, host, route-value, opaque-ID, Product, or proof authority.
3. Fixed public feeds are usable only after repository-native provider/host authority already exists.
4. Payload schemas must validate before they can emit concrete detail candidates.
5. Concrete details still pass unchanged `genuine_job_detail_proof`.
6. The overlay remains monotonic: failed/absent/malformed feeds leave the prior builder result unchanged.
7. No company-name-to-tenant derivation, Workday brute force, guessed POST bodies, guessed form/query values, guessed cross-host delegation, or proof-threshold weakening is admitted.

Current first tranche:

- SuccessFactors: same-authority `/sitemap.xml`, then bounded `/sitemal.xml` RSS fallback;
- Softgarden: canonical `*.career.softgarden.de` `/jobs.feed.json`;
- Recruitee: authorized canonical tenant `/api/offers`;
- d.vinci: authorized `*.dvinci.de` `/jobPublication/list.json?fields=small`, preserving an already-observed `/portal/<name>` prefix.

### Product V1 view type stability

Source: branch-only `hotfix/product-v1-view-type-stability`, commit `235dfe955e28dfd4e7b4fcd5e0bb7db1a1fc7740`.

Current main had lost the two type-preserving casts from that historical hotfix. The harvested migration blob restores only the net two-line semantic delta:

- `overall_quality_score` is explicitly `NUMERIC(6, 2)`;
- initial recursive `product_rank` is explicitly `BIGINT`.

This protects PostgreSQL `CREATE OR REPLACE VIEW` column-type stability. The old branch ancestry is not imported.

## Durable knowledge salvaged from PR #647

PR #647's old re-entry sequencing and 40-case/V18 status are historical and must not be restored as current authority. Its reusable acquisition strategy remains valuable and is preserved here:

`documented public API/feed -> observed stable provider protocol -> bounded browser/runtime observation -> search/LLM booster`

This ordering is an acquisition optimization preference, not a global reasoning hierarchy. Every provider-family adapter still requires:

1. already-proven employer origin authority;
2. observed provider family, never guessed;
3. observed tenant/board/site/company identity when the route requires one;
4. provider-owned documented public infrastructure or repeated protocol evidence sufficient for a generic adapter;
5. bounded requests/results/time;
6. structured records that pass the existing runtime/genuine-detail proof boundary;
7. no inference from provider recognition to a guessed route or host.

Credentialed customer APIs, application-submission APIs, guessed tenants, raw secret-bearing response persistence, and Product/source mutation are not authorized by this knowledge.

## Explicitly superseded, not harvested

### PR #663 / `agent/v41-manual-hardening`

The old pre-V41 regression asserted that `applylink` / `externallink` field names did not yet grant candidate-URL recognition. That exact invariant is stale after qualified later evidence.

Current main intentionally includes `applylink` and `externallink` in runtime `URL_KEYS`, while keeping them outside `EXPLICIT_JOB_KEYS`. Current tests prove the stronger surviving boundary:

- the aliases may identify a candidate URL;
- they do not by themselves grant explicit-job authority;
- they do not grant unrelated cross-host authority;
- they do not make `runtime_job_record_proof` pass;
- they do not promote negative/non-job containers.

Therefore the old #663 test must not be restored.

### `agent/630-workday-cxs-acquisition`

The branch-only V4 Workday integration is semantically subsumed by the current dedicated Workday acquisition architecture.

Current main preserves and strengthens the capability as:

`authorized employer/Workday root -> exact CXS inventory POST -> same-board externalPath -> exact same-host CXS detail GET -> unchanged genuine_job_detail_proof`

The implementation lives in `employer_origin_workday_navigation.py`, `employer_origin_workday_acquisition.py`, Workday detail helpers, dedicated tests, and the builder V4 adapter. No tenant/site/job identity is guessed.

The old direct integration into `employer_origin_acquisition_v4_forms.py` should not be revived.

## Previously proven successor cases

- PR #678: ancestry-free harvest explicitly performed by #682.
- PR #684: exact code head subsequently qualified/merged through #685.
- PR #701: implementation reconstructed on repaired main and merged as #703.
- PR #675/#677: retention/work-admission invariant is represented by current `PROJECT-DRJ.json` v3 semantics.
- PR #644: selector weakening intentionally rejected after root-cause proof; preserve only the failure lesson.

## Remaining review rule

A historical ref may move from REVIEW to a retirement candidate only after one of these is proven:

- its qualified semantic content is reachable/equivalent on current main;
- its useful capability has an explicitly identified stronger successor;
- its durable knowledge has been harvested into current repository truth;
- or it was deliberately rejected and the rejection/failure evidence is preserved.

Until then, ambiguity remains PRESERVE/REVIEW and grants no cleanup effect authority.
