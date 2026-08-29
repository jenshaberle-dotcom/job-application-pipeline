# ACQ-GENERALIZATION-90 — deterministic full-population coverage target

Status: active  
Date: 2026-08-29  
Owner issue: `#676`  
Active re-entry: `docs/planning/active/acq_generalization_90_reentry.md`

## Primary metric

Current distinct Employer-Origin candidates: `N = 65`.

Current strict functioning deterministic product coverage:

`36 / 65 = 55.4%`

Target:

`strict_functioning_candidates / all_current_distinct_candidates >= 0.90`

At `N = 65`, minimum passing numerator is `59` (`59/65 = 90.8%`).
`58/65 = 89.2%` is insufficient.

The denominator is dynamic and must not be reduced by suppressing, deleting,
excluding or reclassifying valid candidates to improve the metric. Historical
`36/40` remains the non-regression cohort.

Only a materialized deterministic connector that produces unchanged strict genuine-job
E2E proof under existing authority and side-effect boundaries counts in the numerator.
Reachable origins, provider recognition, builder READY/`recipe_ready`, audit
classifications and bounded live evidence are diagnostic only.

## Development rule

Implementation priority is reusable population lift + evidence strength + boundedness,
never named-employer convenience.

Hard boundaries:

- no company-specific success branches;
- no guessed tenant/site/job IDs, routes, query values or POST bodies;
- no proof or employer/source-authority weakening;
- no provider/LLM/Tavily dependency for deterministic target work;
- no diagnostic DB/source/Bronze/Silver/Product/application writes;
- ambiguous evidence fails closed;
- every residual rewrite remains monotonic;
- only deterministic-exhausted residuals later enter booster engineering.

## Qualified progress

### Balanced Origin V2

- Origin first failures `18 -> 8`;
- earlier regressions `0`.

### Provider/inventory V3

- inventory first failures `17 -> 16`;
- detail first failures `15 -> 16`;
- `x1f` advanced from inventory to detail through existing Personio inventory;
- earlier regressions `0`.

### Workday CXS V4

Generic path:

`authorized employer/Workday root -> exact CXS inventory POST -> same-board externalPath -> exact same-host CXS detail GET -> unchanged genuine_job_detail_proof`

No tenant/site/job guessing and no proof weakening.

### Evidence-bounded portal delegation

Generic first-party -> portal handoff is permitted only from a strong explicit CTA
plus bounded destination binding. Ambiguity fails closed.

### Builder V5 live replay

Qualified V5 merge: PR `#685`, merge
`45f99c1919e6869451b6301bf41a6d3d12ba7c78`.

Canonical WSL replay on
`main@05f6a137beb34abfb7cc53669c70c3792a7901e3`:

- V3 READY `21/65`;
- V4 READY `22/65`;
- V5 READY `22/65`;
- Workday promotions `1` -> `clarios_germany`;
- portal promotions `0`;
- earlier regressions `0`.

Post-V5 first failures:

- origin `8`;
- origin_reachability `1`;
- inventory `15`;
- detail `16`;
- proof `3`.

Product coverage remains `36/65`.

## Inventory re-cluster

Read-only audit of the `15` inventory residuals produced:

- authorized provider without executable inventory: `2` (`adesso`, `hannover_ruck`);
- client-rendered/script primary: `1`;
- external jobish anchor not promoted: `2`;
- same-origin jobish anchor not classified: `3`;
- low-signal: `7`.

The evidence-rich bridge subset produced provider-route gap `2`, same-origin
vocabulary hypothesis `6`, external vocabulary hypothesis `4`. Navigation-vocabulary
counts contain noise and are not ranked by count alone.

## SuccessFactors common carrier — rejected

PR `#688` added a bounded read-only carrier audit and merged at
`2b37c89ecf1d4821e4c82f703780138af8744367` with Pipeline CI `#896` and Re-entry
`#1479` successful.

Live two-case result:

- `hannover_ruck`: explicit same-host GET `/search/` form;
- `adesso`: no explicit search-route literal;
- same-host `platform/js/search/search.js` on both exposed no explicit route literal;
- total GETs `4`;
- query values persisted `0`;
- provider/LLM/Tavily requests `0`;
- DB writes `0`.

Therefore a universal SuccessFactors -> `/search/` mapping would be guessed route
authority. No adapter is promoted. Durable stop record: issue `#676` comment
`5463886222`.

## Current frontier — 16 detail residuals

The largest remaining downstream technical block is the `16` detail residuals. They
already have deterministic inventory/navigation evidence but the current bounded V4
path does not resolve a concrete detail identity.

PR `#690` added a pure read-only detail-surface measurement gate:

- script: `scripts/run_deterministic_detail_surface_audit.py`;
- tests: `tests/test_deterministic_detail_surface_audit.py`;
- qualified head: `7ca8da9ea372dd968481af81b354cc2b5d628811`;
- Pipeline CI `#900`: success including full suite;
- Re-entry `#1490`: success;
- merge: `aed89b99a25d973c6aef68d291be548f25df123e`.

Boundary:

- only V5 `detail` first failures;
- existing V4 path replay only;
- max `4` HTTPS GETs per candidate;
- no guessed routes/IDs/query values/POST bodies;
- query values are never persisted;
- provider/LLM/Tavily requests `0`;
- DB/source/Product/application writes `0`;
- connector materialization `0`.

The audit separates possible reusable classes such as strict existing query details,
unknown identifier-like query-key surfaces, form-driven details, unclassified jobish
anchors, client-rendered/script surfaces, provider detail-route gaps and low-signal
cases. All such classifications remain diagnostic until a narrower evidence proof
qualifies an implementation.

Canonical next gate:

```bash
.venv/bin/python -m scripts.run_deterministic_detail_surface_audit \
  --layer-audit /tmp/deterministic_connector_builder_layer_audit_v5.json \
  --output /tmp/deterministic_detail_surface_audit_v5.json
```

Acceptance for this gate:

1. input count is the expected `16` detail residuals;
2. exact classification cohorts and request totals are captured;
3. technical replay errors are separated from semantic evidence;
4. no product-coverage movement is claimed;
5. the next capability is chosen by reusable lift + evidence strength + boundedness;
6. diagnostic-only classes receive a narrower evidence proof before production logic.

Continue deterministic hardening until no reasonable bounded generic deterministic
class remains. Only then may exhausted residuals enter the booster path.

## Workspace / continuation

The 2026-08-28 workspace migration is closed and delivered through PR `#682`.
Historical migration checkpoint MD/JSON remain retained provenance. Every mutating
ACQ-676 slice begins from freshly observed current `origin/main` in a declared
feature branch/worktree.

Canonical continuation authority is the active re-entry MD/JSON plus live issue
`#676` evidence.
