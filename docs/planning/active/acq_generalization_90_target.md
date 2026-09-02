# ACQ-GENERALIZATION-90 — deterministic full-population coverage target

Status: active  
Date: 2026-09-02  
Owner issue: `#676`  
Active re-entry: `docs/planning/active/acq_generalization_90_reentry.md`

## Primary metric

Strict functioning deterministic product coverage across all current distinct Employer-Origin candidates remains the only primary product metric.

Current denominator:

- distinct candidates: `65`;
- historical connector-present cohort: `40/65`;
- strict functioning deterministic product coverage: `36/65 = 55.4%`;
- minimum passing numerator at N=65: `59` (`59/65 = 90.8%`).

The denominator must not be reduced by suppressing or reclassifying valid candidates. Diagnostic READY/`recipe_ready`, provider recognition or audit evidence never counts as product coverage by itself.

## Product success contract

A candidate enters the numerator only after a materialized deterministic connector path passes unchanged strict genuine-job acquisition proof under existing employer/source authority and side-effect boundaries.

No deterministic hardening slice may:

- add company-specific success branches when a generic class is possible;
- guess tenant/site/job IDs, routes, query/form values or POST bodies;
- weaken proof or employer/source authority;
- convert diagnostic evidence directly into product coverage;
- require LLM/Tavily/provider search for the deterministic target path.

## Qualified deterministic stack

Retained generic capabilities through V5:

- balanced Origin V2;
- provider/inventory V3;
- Workday CXS deterministic acquisition;
- evidence-bounded portal delegation;
- Builder V5 monotonic residual rewrite/composition.

V5 live replay remains:

- READY `22/65` diagnostic;
- Workday promotions `1` (`clarios_germany`);
- portal promotions `0`;
- residuals: Origin `8`, Origin reachability `1`, Inventory `15`, Detail `16`, Proof `3`;
- product coverage unchanged `36/65`.

## Closed residual measurements

### SuccessFactors `/search/`

The strongest SuccessFactors inventory pair (`adesso`, `hannover_ruck`) did not prove one common evidence-backed `/search/` route. A universal SuccessFactors `/search/` rule remains rejected.

### Detail reclassification

The 16 Detail residuals were reduced to:

- `10` unclassified-jobish;
- `5` form-driven;
- `1` semantic query-ID: IPH `weobjectid x12`.

### Form carrier gate

The five form-driven cases were audited offline. Result:

- `2` GET jobish forms without semantic identifier;
- `2` GET jobish search/filter forms;
- `1` POST jobish search/filter form;
- cross-company signatures `0`;
- reusable semantic identifier carrier `0`.

This is a negative evidence stop. No deterministic form adapter is authorized from this cohort.

## V6 provider public-feed salvage

PR `#705` merged the qualified ancestry-free V6 provider-capability tranche onto current-main ancestry after Pipeline CI `#933` and Re-entry `#1577` succeeded.

V6 adds fixed provider-wide public-feed capability only after existing provider/host authority:

- SuccessFactors: `/sitemap.xml`, then `/sitemal.xml` RSS fallback;
- Softgarden: `/jobs.feed.json`;
- Recruitee: `/api/offers`;
- d.vinci: `/jobPublication/list.json?fields=small` with an already-observed portal prefix when present.

The V6 overlay may touch only V5 Inventory/Detail residuals, uses GET-only public-feed requests capped at three per eligible residual, performs no DB/Product/source writes and keeps `genuine_job_detail_proof` unchanged.

## Post-migration workspace gate

This repository's `POST-MIGRATION-RESTART.json` is now `PASS` after the 2026-09-02 canonical WSL cleanup/reinspection:

- clean canonical `main` equals fresh `origin/main`;
- exactly one persistent checkout remains;
- no non-main project worktree remains;
- no local non-main branch remains;
- harvested unique value is versioned on current-main ancestry;
- no remote branch was deleted.

The shared portfolio restart contract still requires **all ten managed projects PASS** before active project development resumes. Therefore the V6 benchmark is the next engineering measurement, but remains portfolio-gated until that condition is true.

## Current deterministic frontier

Once portfolio restart authority is satisfied, run V6 against the same 65-candidate DB population:

```bash
.venv/bin/python -m scripts.run_deterministic_connector_builder_layer_audit_v6 \
  --output /tmp/deterministic_connector_builder_layer_audit_v6.json
```

Measure:

- `V5_READY -> V6_READY`;
- public-feed attempted count;
- public-feed promoted count and exact company keys;
- updated first-failure distribution;
- any regression (must be zero under the monotonic overlay contract).

## Decision order

1. Run the same-population V6 benchmark only after portfolio all-PASS restart authority.
2. Accept a V6 class only when provider/host authority, feed schema, concrete detail and unchanged proof all hold.
3. Do not move `36/65` for diagnostic READY alone.
4. Re-cluster residuals after measured V6 lift.
5. If V6 produces no reusable provider-bound lift, audit the `10` jobish Detail cases with bounded anchor/path-shape evidence; do not globally widen vocabulary.
6. Keep IPH `weobjectid` deferred unless broader evidence makes it reusable.
7. Continue deterministic hardening until no reasonable generic bounded class remains.
8. Materialize stable recipes and update product coverage only after unchanged strict E2E product proof.
9. Only exhausted residuals enter later booster engineering; productive decision order remains deterministic -> ML -> booster.
