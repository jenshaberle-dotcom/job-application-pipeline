# ACQ-GENERALIZATION-90 — canonical re-entry

Status: **ACTIVE — SUCCESSFACTORS COMMON CARRIER REJECTED; DETAIL RESIDUAL SURFACE AUDIT NEXT**  
Owner issue: `#676`  
Migration delivery merge: `6af34cb54a9bbf29ffc257d1109f495d08d1678d`  
Builder V5 merge: `45f99c1919e6869451b6301bf41a6d3d12ba7c78`  
Latest qualified diagnostic merge: `aed89b99a25d973c6aef68d291be548f25df123e`

Machine-readable companion: `docs/planning/active/acq_generalization_90_reentry.json`.

## Authority

This file is the active ACQ-676 continuation anchor. Repository truth, bounded live
evidence, tests and CI override chat summaries. Every mutating ACQ-676 slice starts
from freshly observed current `origin/main` in a declared feature branch/worktree.
Historical #676 branches are never continuation authority.

Read first:

1. `PROJECT-HYGIENE.json`;
2. `PROJECT-LOCAL-WORKSPACE.json`;
3. `PROJECT-DRJ.json`;
4. `docs/current/README.md`;
5. this file;
6. `acq_generalization_90_target.md`;
7. live issue `#676` and current PR state;
8. current `origin/main`, branch/worktree relationship and latest CI.

## Canonical product metric

Current strict functioning deterministic product coverage remains:

`36 / 65 = 55.4%`

Target at the current denominator:

`>= 59 / 65 = 90.8%`

Historical `36/40` remains the regression cohort. Builder READY/`recipe_ready`,
provider recognition, audit classifications and bounded live rescue evidence are
never product-coverage credit. Numerator movement requires a materialized connector
that passes unchanged strict E2E acquisition proof under existing authority and
side-effect boundaries.

## Architecture already qualified

Do not repeat without changed repository/live evidence:

- balanced Origin V2: Origin first failures `18 -> 8`, earlier regressions `0`;
- provider/inventory V3: inventory `17 -> 16`, detail `15 -> 16`, `x1f` advanced to
  detail through existing Personio inventory;
- generic Workday CXS acquisition/proof path;
- evidence-bounded first-party -> portal delegation;
- Builder V5 shared monotonic `rewrite_residual_suffix()` composition contract.

Current V5 order remains:

```text
V3 base
  -> Workday CXS residual adapter
  -> evidence-bounded portal residual adapter
  -> remaining residuals
```

No adapter may move first failure earlier, weaken proof/authority, guess tenant/site/job
identity, or convert diagnostic evidence directly into product authority.

## Qualified V5 live replay — 2026-08-29

Canonical WSL replay completed on
`main@05f6a137beb34abfb7cc53669c70c3792a7901e3`.

Exact transition:

- V3 READY: `21/65`;
- V4 READY: `22/65`;
- V5 READY: `22/65`;
- Workday promotions: `1` -> `clarios_germany`;
- portal promotions: `0`;
- earlier-stage regressions: `0`.

Final V5 first-failure population:

- READY: `22`;
- origin: `8`;
- origin_reachability: `1`;
- inventory: `15`;
- detail: `16`;
- proof: `3`.

Exact detail cohort:

`1_1, amadeus_fire, aok_niedersachsen_die_gesundheitskasse, bjak, compugroup_medical, deloitte, genoverband_e_v, iph_institut_fur_integrierte_produktion_hannover_ggmbh, land_niedersachsen, msg_systems, mtu_maintenance, triology, tuv_sud, x1f, yer_deutschland, zscaler_germany`

Durable V5 checkpoint: issue `#676` comment `5462507864`.

## Inventory residual re-cluster — completed

Read-only inventory surface audit across the `15` inventory residuals:

- authorized provider without executable inventory: `2` -> `adesso`, `hannover_ruck`;
- client-rendered/script primary: `1`;
- external jobish anchor not promoted: `2`;
- same-origin jobish anchor not classified: `3`;
- low-signal inventory surface: `7`.

Evidence-rich bridge audit:

- same-origin listing-vocabulary hypothesis: `6`;
- external listing-vocabulary hypothesis: `4`;
- provider-route-adapter gap: `2` -> `adesso`, `hannover_ruck`.

Raw vocabulary counts contain navigation noise and were not treated as implementation
priority by count alone.

## SuccessFactors common carrier — measured and rejected

PR `#688` merged the bounded read-only SuccessFactors carrier measurement tool:

- merge: `2b37c89ecf1d4821e4c82f703780138af8744367`;
- Pipeline CI `#896`: success;
- Re-entry `#1479`: success;
- max `2` GETs per eligible candidate;
- no guessed routes/tenants/IDs/POST bodies/query values;
- query values persisted: `0`;
- provider/LLM/Tavily requests: `0`;
- DB/Product/source/application writes: `0`.

Canonical live carrier audit then completed on the two eligible cases with exactly
`4` GETs total:

- `hannover_ruck`: `explicit_root_get_search_form`; exact same-host GET action
  `/search/` with observed field names;
- `adesso`: `no_explicit_search_route_literal`; no root GET search form;
- both explicitly embedded same-host `platform/js/search/search.js` resources exposed
  no explicit search-route literal under the bounded classifier;
- script evidence for both: `no_explicit_search_route_literal`.

Conclusion:

> No common evidence-backed SuccessFactors inventory carrier was proven.

A generic SuccessFactors -> `/search/` mapping would be guessed route authority and is
therefore rejected. The provider family may later split if a separately evidenced
reusable subgroup appears, but no adapter is promoted from this gate.

Durable stop record: issue `#676` comment `5463886222`.

Product coverage remains `36/65`.

## Detail residual measurement frontier

The largest remaining downstream technical block is now the `16` detail residuals.
These cases already have deterministic inventory/navigation evidence; the current
bounded V4 path did not resolve a concrete detail identity.

PR `#690` added the bounded read-only detail-surface audit:

- script: `scripts/run_deterministic_detail_surface_audit.py`;
- tests: `tests/test_deterministic_detail_surface_audit.py`;
- qualified head: `7ca8da9ea372dd968481af81b354cc2b5d628811`;
- Pipeline CI `#900`: success, including full suite;
- Re-entry `#1490`: success on Ubuntu and Windows;
- merge: `aed89b99a25d973c6aef68d291be548f25df123e`.

Boundary:

- input only V5 `first_failure_layer == detail`;
- replay uses existing V4 acquisition semantics;
- hard cap `4` HTTPS GETs per candidate;
- no guessed routes, tenants, IDs, POST bodies or query values;
- query **values** are never persisted; only structural query-key names/counts may be
  recorded;
- no provider/LLM/Tavily calls;
- no DB/source/Bronze/Silver/Product/application writes;
- no connector materialization;
- unknown identifier-like query keys are diagnostic evidence only;
- if current V4 now resolves a detail due live drift, that is recorded separately and
  is not credited as a new capability.

Diagnostic classes include:

- `current_v4_now_resolves_detail`;
- `strict_query_detail_already_visible`;
- `unknown_query_identifier_key_surface`;
- `form_driven_detail_surface`;
- `unclassified_jobish_detail_surface`;
- `client_rendered_or_script_detail_surface`;
- `provider_detail_route_gap`;
- `low_signal_detail_surface`.

## Canonical next command

From clean canonical WSL `main` after fast-forwarding `origin/main`:

```bash
.venv/bin/python -m scripts.run_deterministic_detail_surface_audit \
  --layer-audit /tmp/deterministic_connector_builder_layer_audit_v5.json \
  --output /tmp/deterministic_detail_surface_audit_v5.json
```

Module execution from repository root is canonical for scripts importing `scripts.*`
and `src.*`.

## Sole continuation sequence

1. Fast-forward canonical WSL `main` to current `origin/main`; require clean identity.
2. Run the bounded detail-surface audit above against the qualified V5 artifact.
3. Verify input count `16`, inspect exact classification counts/cohorts, and record
   request totals/errors. Do not change product coverage.
4. Select the strongest reusable detail class by population lift + evidence strength +
   boundedness.
5. Before implementation, perform a narrower evidence proof for that exact class if
   the surface audit is only diagnostic.
6. Promote only a generic fail-closed capability with unchanged proof and employer
   authority; otherwise record the stop reason and move to the next class.
7. Re-run the relevant population gate after every meaningful promotion.
8. Continue deterministic hardening until no reasonable bounded generic class remains.
9. Materialize stable evidence-backed recipes and update product coverage only from
   unchanged strict E2E proof; only exhausted residuals may enter booster engineering.

## Retention / DRJ

ACTIVE / KEEP:

- issue `#676`;
- current `main`;
- this re-entry MD/JSON and target;
- V1-V5 builder audit chain;
- inventory surface/bridge audits;
- SuccessFactors carrier audit as negative-evidence provenance;
- detail-surface audit + tests;
- merged Origin V2, Workday and portal implementations;
- builder residual-rewrite contract.

PRESERVE provenance:

- migration checkpoint MD/JSON;
- issue comments `5462507864`, `5462664378`, `5463886222`;
- PR histories `#682`, `#685`, `#687`, `#688`, `#689`, `#690` and qualified gates.

Merged/superseded feature branches have no continuation authority, but branch/worktree
deletion remains a separate DRJ technical effect requiring fresh local observation.
Age, path or name are never deletion authority. `DRJ-RECONCILE-REQUEST.json` remains
`NO_REQUEST` unless fresh exact local hygiene evidence requires otherwise.
