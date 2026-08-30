# ACQ-GENERALIZATION-90 — canonical re-entry

Status: **ACTIVE — DETAIL LIVE AUDIT + ID RECLASSIFICATION COMPLETE; FORM CARRIER AUDIT NEXT**  
Owner issue: `#676`  
Migration delivery merge: `6af34cb54a9bbf29ffc257d1109f495d08d1678d`  
Builder V5 merge: `45f99c1919e6869451b6301bf41a6d3d12ba7c78`  
Latest qualified diagnostic merge: `e8aa41179e6618fa96b33e82ec57dd51edd1a0f5`

Machine-readable companion: `docs/planning/active/acq_generalization_90_reentry.json`.

## Authority

Repository truth, bounded live evidence, tests and CI override chat summaries. Every
mutating ACQ-676 slice starts from freshly observed current `origin/main` in a declared
feature branch/worktree. Historical #676 branches are never continuation authority.

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

Strict functioning deterministic product coverage remains:

`36 / 65 = 55.4%`

Target at the current denominator:

`>= 59 / 65 = 90.8%`

Historical `36/40` is the regression cohort. Builder READY/`recipe_ready`, provider
recognition and audit classifications are diagnostic only. Numerator movement requires
a materialized connector that passes unchanged strict E2E acquisition proof under
existing authority and side-effect boundaries.

## Qualified deterministic stack

Already merged and retained:

- balanced Origin V2: Origin first failures `18 -> 8`, earlier regressions `0`;
- provider/inventory V3;
- generic Workday CXS deterministic acquisition;
- evidence-bounded portal delegation;
- Builder V5 monotonic `rewrite_residual_suffix()` composition contract.

V5 live replay on `main@05f6a137beb34abfb7cc53669c70c3792a7901e3`:

- V3 READY `21/65`;
- V4 READY `22/65`;
- V5 READY `22/65`;
- Workday promotions `1` -> `clarios_germany`;
- portal promotions `0`;
- final first failures: Origin `8`, Origin reachability `1`, Inventory `15`, Detail `16`, Proof `3`;
- product coverage unchanged `36/65`.

Durable replay checkpoint: issue `#676` comment `5462507864`.

## Inventory frontier — measured

The 15 Inventory residuals were structurally re-clustered. The strongest provider pair
was `adesso` + `hannover_ruck`, both authorized SuccessFactors surfaces. A focused
carrier audit proved that the pair does **not** share one evidence-backed inventory
route: Hannover Re exposes an explicit GET `/search/` form while adesso does not.
Therefore a generic SuccessFactors -> `/search/` rule is rejected as guessed route
authority.

Durable stop record: issue `#676` comment `5463886222`.

## Detail live audit — completed

PR `#690` merged `scripts/run_deterministic_detail_surface_audit.py` at
`aed89b99a25d973c6aef68d291be548f25df123e` with Pipeline CI `#900` and Re-entry
`#1490` successful.

Canonical live run across the 16 V5 Detail residuals completed with:

- input cases: `16`;
- HTTP GETs: `45`;
- max GETs/candidate: `4`;
- replay errors: `0`;
- provider requests: `0`;
- DB writes: `0`;
- query values persisted: `0`;
- raw classes: unknown-query-ID `8`, unclassified-jobish `5`, form-driven `3`.

The raw unknown-query-ID class was intentionally diagnostic and required a second
measurement gate because substring `id` matching admitted tracking/CMS noise.

## Identifier reclassification — completed

PR `#692` merged zero-network
`scripts/run_deterministic_detail_identifier_reclassification.py` at
`5d8aa447f4de13349e411584997fdbe95f2e1eba` with Pipeline CI `#904` and Re-entry
`#1502` successful.

The live offline reclassification produced:

- network requests: `0`;
- DB reads/writes: `0/0`;
- query values read/persisted: `0/0`;
- before: unknown-query-ID `8`, unclassified-jobish `5`, form-driven `3`;
- after: unknown-query-ID `1`, unclassified-jobish `10`, form-driven `5`;
- changed candidates: `1_1, amadeus_fire, aok_niedersachsen_die_gesundheitskasse, bjak, compugroup_medical, deloitte, land_niedersachsen`;
- retained semantic identifier: `iph_institut_fur_integrierte_produktion_hannover_ggmbh -> weobjectid x12`;
- seven noisy ID-like key families suppressed.

Durable checkpoint: issue `#676` comment `5467283456`.

Interpretation:

- the nominal 8-case query-ID population was measurement noise and does not authorize a
  generic query-ID adapter;
- IPH `weobjectid` is a real but single-employer semantic candidate and is not current
  priority by population lift;
- the remaining Detail population is now `10 jobish / 5 form-driven / 1 semantic-ID`.

## Current frontier — form carrier audit

The `5` form-driven residuals are the strongest next bounded class because the existing
immutable artifacts already contain form method, action URL shape and field names.
No new network request or form submission is required to determine whether a reusable
carrier exists.

PR `#693` merged the zero-network measurement tool:

- script: `scripts/run_deterministic_detail_form_carrier_audit.py`;
- tests: `tests/test_deterministic_detail_form_carrier_audit.py`;
- qualified head: `95b8c02d7bbc14363d3a6658a2c3b1597153f630`;
- Pipeline CI `#906`: success including full suite;
- Re-entry `#1507`: success;
- merge: `e8aa41179e6618fa96b33e82ec57dd51edd1a0f5`.

Hard boundary:

- consumes only the existing identifier-reclassification artifact;
- network requests `0`;
- form submissions `0`;
- form/query values read `0`;
- DB/provider/LLM/Tavily requests/writes `0`;
- connector materialization `0`;
- GET search/filter forms remain distinct from semantic-ID detail forms;
- POST forms are diagnostic only and never executable authority.

## Canonical next command

From clean canonical WSL `main` after fast-forwarding `origin/main`:

```bash
.venv/bin/python -m scripts.run_deterministic_detail_form_carrier_audit \
  --reclassification /tmp/deterministic_detail_identifier_reclassification_v1.json \
  --output /tmp/deterministic_detail_form_carrier_audit_v1.json
```

## Sole continuation sequence

1. Fast-forward clean canonical WSL `main` to current `origin/main`.
2. Run the zero-network form carrier audit above against the existing reclassification artifact.
3. Require input count `5`; inspect exact carrier classes and cross-company signatures.
4. If a reusable fail-closed carrier appears on multiple employers, perform the narrowest
   evidence proof needed before implementation; do not infer missing form values or POST bodies.
5. If the form cohort splits, record the stop reason and move to the 10-case jobish cohort with
   a focused bounded anchor/path audit rather than global vocabulary widening.
6. Treat IPH `weobjectid` as a later single-case capability unless broader evidence appears.
7. Continue deterministic hardening until no reasonable bounded generic class remains.
8. Materialize only stable evidence-backed recipes and change product coverage only from
   unchanged strict E2E proof; exhausted residuals alone may enter booster engineering.

## Retention / DRJ

ACTIVE / KEEP:

- issue `#676`;
- current `main`;
- this re-entry MD/JSON and target;
- V1-V5 builder audit chain;
- inventory surface/bridge and SuccessFactors negative-evidence audits;
- detail surface audit, identifier reclassification and form carrier audit + tests;
- merged Origin V2, Workday and portal implementations;
- builder residual-rewrite contract.

PRESERVE provenance:

- migration checkpoint MD/JSON;
- issue comments `5462507864`, `5463886222`, `5467129927`, `5467283456`;
- PR histories `#682`, `#685`, `#687`, `#688`, `#689`, `#690`, `#691`, `#692`, `#693`.

Merged feature branches have no continuation authority, but branch/worktree deletion is a
separate DRJ technical effect requiring fresh local observation. Age, path or name are
never deletion authority. `DRJ-RECONCILE-REQUEST.json` remains `NO_REQUEST` unless fresh
exact local hygiene evidence requires otherwise.
