# ACQ-GENERALIZATION-90 — deterministic full-population coverage target

Status: active  
Date: 2026-08-29  
Owner issue: `#676`  
Active re-entry: `docs/planning/active/acq_generalization_90_reentry.md`

## Primary metric

The primary deterministic acquisition metric is strict functioning deterministic
coverage across the complete current distinct Employer-Origin candidate population.

Current denominator from the 2026-08-28 market refresh:

- distinct current candidates: `N = 65`;
- connector-present cohort: `40/65`;
- strict functioning deterministic product coverage: `36/65 = 55.4%`;
- fresh out-of-sample candidates at issue open: `10`;
- fresh candidates with a strict functioning connector at issue open: `0/10`.

Target:

`strict_functioning_candidates / all_current_distinct_candidates >= 0.90`

At `N = 65`, the minimum passing numerator is `59` (`59/65 = 90.8%`).
`58/65 = 89.2%` is insufficient.

The denominator is dynamic and must not be reduced by suppressing, deleting,
excluding or reclassifying valid candidates merely to improve the metric.

## What counts as success

A candidate counts in the product numerator only when the deterministic stack can
produce unchanged strict genuine-job acquisition proof under the repository's
existing employer/source authority and side-effect boundaries through a materialized
connector path.

The following are diagnostic/evidence states only and do not count by themselves:

- reachable career/origin URL;
- provider recognition;
- builder `recipe_ready` / READY;
- generated recipe/connector without strict E2E proof;
- bounded live rescue evidence not yet materialized and exercised through the
  canonical product path.

The historical `36/40` remains a non-regression cohort. Canonical product coverage
remains `36/65` until new materialized strict E2E evidence proves otherwise.

## Root-cause phase — completed

The fresh `0/10` was shown to cluster into reusable technical classes rather than ten
independent employer-specific connector gaps. The main classes include:

1. origin enumeration/budget architecture;
2. acronym/compact-brand discovery;
3. parent/subsidiary identity composition;
4. first-party -> portal/provider delegation;
5. client-rendered/API-backed inventories;
6. provider/query vocabulary gaps.

Implementation priority remains reusable population lift + evidence strength +
boundedness, never named-employer convenience.

## Qualified deterministic progress

### Balanced Origin V2

Observed live result:

- Origin first-failures: `18 -> 8`;
- prior Origin failures advanced: `10/18`;
- earlier-stage regressions: `0`.

### Provider/inventory V3

Observed result:

- diagnostic READY: `21/65`;
- Inventory first-failures: `16`;
- Detail first-failures: `16`;
- `x1f`: `inventory -> detail` through existing Personio inventory;
- earlier-stage regressions: `0`.

### Workday CXS V4

Generic deterministic composition:

`authorized employer/Workday root -> exact CXS inventory POST -> same-board externalPath -> exact same-host CXS detail GET -> unchanged genuine_job_detail_proof`

No tenant/site/job guessing, no company-specific branch, no proof weakening, no
provider/LLM/Tavily requirement and no diagnostic product writes.

### Evidence-bounded portal delegation

Generic first-party -> portal handoff is implemented only from a strong explicit CTA
plus bounded destination binding. Multiple qualifying routes fail closed. No global
listing-vocabulary widening was introduced.

### Builder V5 — live replay completed

Builder V5 merge:

- PR `#685`;
- merge `45f99c1919e6869451b6301bf41a6d3d12ba7c78`;
- Pipeline CI `#887`: success;
- Re-entry `#1454`: success.

Canonical WSL replay completed on
`main@05f6a137beb34abfb7cc53669c70c3792a7901e3`.

Exact live transition:

- V3 READY: `21/65`;
- V4 READY: `22/65`;
- V5 READY: `22/65`;
- Workday promotions: `1` -> `clarios_germany`;
- portal promotions: `0`;
- earlier-stage regressions: `0`.

Final V5 first-failure population:

- origin: `8`;
- origin_reachability: `1`;
- inventory: `15`;
- detail: `16`;
- proof: `3`.

These are diagnostic builder counts; product coverage remains `36/65`.

## Residual re-cluster — completed measurement gate

The 15 Inventory residuals were audited with one root GET maximum each:

- authorized provider without executable inventory: `2` (`adesso`, `hannover_ruck`);
- client-rendered/script primary: `1`;
- external jobish anchor not promoted: `2`;
- same-origin jobish anchor not classified: `3`;
- low-signal: `7`.

The evidence-rich bridge subset produced:

- same-origin listing-vocabulary hypothesis: `6`;
- external listing-vocabulary hypothesis: `4`;
- provider-route-adapter gap: `2` (`adesso`, `hannover_ruck`).

The raw vocabulary counts contain navigation noise and are not ranked above stronger
provider evidence merely because their count is larger.

## Current deterministic frontier — SuccessFactors carrier measurement

The strongest bounded cross-employer residual class is two already-authorized
SuccessFactors career sites with no executable inventory route.

Observed root evidence:

- Hannover Re: explicit same-host GET `/search/` form plus same-host
  `/platform/js/search/search.js`;
- adesso: no root form, but the same explicit same-host search script stack.

This is not enough to infer `/search/` for adesso or to approve a generic adapter.

PR `#688` added only a read-only carrier audit:

- merge `2b37c89ecf1d4821e4c82f703780138af8744367`;
- Pipeline CI `#896`: success;
- Re-entry `#1479`: success;
- max `2` GETs per eligible candidate;
- exact same-host embedded search script only;
- no guessed routes/IDs/POST bodies/query values;
- query values persisted: `0`;
- provider/LLM/Tavily requests: `0`;
- DB/Product/source/application writes: `0`.

Next evidence gate:

```bash
.venv/bin/python -m scripts.run_deterministic_successfactors_search_carrier_audit \
  --layer-audit /tmp/deterministic_connector_builder_layer_audit_v5.json \
  --surface-audit /tmp/deterministic_inventory_surface_audit_v5.json \
  --output /tmp/deterministic_successfactors_search_carrier_audit.json
```

A generic SuccessFactors inventory capability may be implemented only if the live
carrier audit proves a reusable bounded carrier under one generic contract. If the
class splits or fails closed, record the stop reason and move to the next residual
class rather than adding employer-specific rescue logic.

## Guardrails

- no company-specific success branches;
- no guessed tenant/opaque IDs/routes/query values;
- no proof or employer-authority weakening;
- no provider/LLM/Tavily requirement for deterministic target work;
- no diagnostic DB/source/Bronze/Silver/Product/application writes;
- historical 40-case cohort remains a regression control;
- optional layers remain evidence-driven;
- residual rewrites remain monotonic;
- no product-coverage credit from diagnostics alone;
- deterministic hardening continues until no reasonable generic bounded class remains;
- only exhausted residuals enter booster engineering.

## Workspace / continuation

The 2026-08-28 migration is closed and delivered through PR `#682`. Historical
migration checkpoint MD/JSON remain retained provenance. Every mutating ACQ-676 slice
starts from freshly observed current `origin/main` in a declared feature branch or
worktree.

Canonical continuation authority is
`docs/planning/active/acq_generalization_90_reentry.md` plus its JSON companion and
live issue `#676` evidence.
