# ACQ-GENERALIZATION-90 — canonical re-entry

Status: **ACTIVE — POST-MIGRATION RESTART PASS; V6 PUBLIC-FEED SALVAGE MERGED; 65-CANDIDATE V6 BENCHMARK NEXT AFTER PORTFOLIO ALL-PASS**  
Owner issue: `#676`  
Canonical restart/harvest main: `41c855c3858b40a3d2d1d7b84dc8d6488f81d2a9`  
Builder V5 merge: `45f99c1919e6869451b6301bf41a6d3d12ba7c78`  
V6 salvage delivery: PR `#705`, qualified head `7b5ca27e02d93d7fde928093dd8a7a9961e64708`, merge `41c855c3858b40a3d2d1d7b84dc8d6488f81d2a9`

Machine-readable companion: `docs/planning/active/acq_generalization_90_reentry.json`.

## Authority and workspace

Repository truth, bounded live evidence, tests and CI override chat summaries.

Every future mutating ACQ-676 slice must:

1. start from freshly observed current `origin/main`;
2. use a declared temporary worktree under the repository workspace contract;
3. never use branch-of-branch or historical branch ancestry as continuation authority;
4. preserve qualified historical content by ancestry-free reconstruction when needed;
5. keep DRJ retention status separate from project work-admission authority.

The one-time project post-migration restart gate is now **PASS**. Host proof on 2026-09-02 established:

- repository ID `1230805345` and canonical origin matched;
- exactly one persistent checkout remains at `$HOME/projects/job-application-pipeline`;
- it is clean `main` and equals fresh `origin/main@41c855c3858b40a3d2d1d7b84dc8d6488f81d2a9`;
- no non-main project worktree remains;
- all local non-main branches were semantically classified before retirement;
- no dirty, unpushed, divergent, detached or ambiguous local state remains;
- no remote branch was deleted.

Durable harvest/restart evidence: issue `#704`, `POST-MIGRATION-RESTART.json`, and `docs/knowledge/branch_salvage_704.md`.

**Portfolio boundary:** the shared post-migration contract requires all ten managed projects to reach `PASS` before active project development resumes. Therefore the V6 benchmark below is the next ACQ-676 engineering action, but it is not executable authority until the portfolio all-PASS gate is satisfied.

## Canonical product metric

Strict functioning deterministic product coverage remains:

`36 / 65 = 55.4%`

Target at the current denominator:

`>= 59 / 65 = 90.8%`

Historical `36/40` is regression evidence only. Builder READY/`recipe_ready`, provider recognition and audit classifications remain diagnostic. Numerator movement requires a materialized connector that passes unchanged strict E2E acquisition proof.

## Qualified deterministic stack through V5

Retained generic capabilities:

- balanced Origin V2: Origin first failures `18 -> 8`, earlier regressions `0`;
- provider/inventory V3;
- generic Workday CXS deterministic acquisition;
- evidence-bounded portal delegation;
- Builder V5 monotonic `rewrite_residual_suffix()` composition.

V5 live replay:

- V3 READY `21/65`;
- V4 READY `22/65`;
- V5 READY `22/65`;
- Workday promotion `1`: `clarios_germany`;
- portal promotions `0`;
- first failures: Origin `8`, Origin reachability `1`, Inventory `15`, Detail `16`, Proof `3`;
- product coverage unchanged `36/65`.

Durable checkpoint: issue `#676` comment `5462507864`.

## Inventory and Detail evidence already closed

### SuccessFactors `/search/` carrier

The focused `adesso` + `hannover_ruck` audit did not prove one common evidence-backed `/search/` route. A universal SuccessFactors `/search/` rule remains rejected as guessed route authority.

Checkpoint: issue `#676` comment `5463886222`.

### Detail live audit and identifier reclassification

The 16 Detail residuals completed the bounded live audit and zero-network semantic reclassification:

- final split: `10` unclassified-jobish, `5` form-driven, `1` semantic query-ID;
- retained single semantic identifier: `iph_institut_fur_integrierte_produktion_hannover_ggmbh -> weobjectid x12`;
- seven tracking/CMS ID-like families were suppressed;
- no product coverage change.

Checkpoint: issue `#676` comment `5467283456`.

### Form carrier audit — completed negative gate

The five form-driven cases were audited offline with zero network, zero submissions, zero form/query values read, zero DB/provider/LLM/Tavily activity and zero materialization.

Measured result:

- input form-driven cases: `5`;
- classes: `get_jobish_form_without_semantic_identifier=2`, `get_jobish_search_or_filter_form=2`, `post_jobish_search_or_filter_form=1`;
- cross-company signatures: `0`;
- reusable semantic identifier carrier: none.

Conclusion: **no generic deterministic form carrier is authorized for this cohort**. Do not implement these forms and do not infer POST bodies or form values.

## V6 external/historical deterministic salvage — merged

PR `#705` ancestry-free reconstructed the qualified V6 content from fresh current-main ancestry and merged after:

- Pipeline CI `#933`: success;
- Re-entry `#1577`: success;
- merge: `41c855c3858b40a3d2d1d7b84dc8d6488f81d2a9`.

The previous PR `#695` was closed only after this qualified successor was merged.

V6 adds a monotonic residual overlay above unchanged V5 for already-authorized provider/host evidence:

- SuccessFactors: same-authority `/sitemap.xml`, then bounded `/sitemal.xml` RSS fallback;
- Softgarden: canonical `*.career.softgarden.de` `/jobs.feed.json`;
- Recruitee: authorized canonical tenant `/api/offers`;
- d.vinci: authorized `*.dvinci.de` `/jobPublication/list.json?fields=small`, preserving an already-observed `/portal/<name>` prefix.

Hard exclusions remain:

- no company-name -> tenant/slug derivation;
- no Workday shard/board brute force;
- no guessed routes, opaque IDs, form/query values or POST bodies;
- no guessed cross-host feed authority;
- no external dataset row as Product proof;
- no proof-threshold weakening.

Promotion requires: existing provider/host authority -> validated provider feed -> concrete detail URL -> fetch -> unchanged `genuine_job_detail_proof`.

## Canonical next engineering action — portfolio-gated

Once the shared portfolio restart contract reports **all ten projects PASS**, run the same 65-candidate cohort through V6 from clean canonical WSL `main`:

```bash
.venv/bin/python -m scripts.run_deterministic_connector_builder_layer_audit_v6 \
  --output /tmp/deterministic_connector_builder_layer_audit_v6.json
```

Expected measurement surface:

- `V5_READY`;
- `V6_READY`;
- `PUBLIC_FEED_ATTEMPTED`;
- `PUBLIC_FEED_PROMOTED`;
- exact promoted company keys;
- updated first-failure distribution in the JSON artifact;
- DB writes `0`;
- provider/LLM/Tavily requests `0`.

V6 network activity is GET-only and capped at three public-feed requests per eligible Inventory/Detail residual. The script reads the DB candidate population but does not write Product/source/Bronze/Silver/application state.

## Continuation after the V6 replay

1. Compare V5 -> V6 on the identical 65-candidate population.
2. Treat only strict V6 promotions as evidence for a reusable capability; diagnostic READY still does not move product coverage.
3. Re-cluster the remaining first failures after measured V6 lift.
4. If V6 yields no reusable provider-bound lift, move to the bounded 10-case jobish Detail anchor/path-shape audit rather than global vocabulary widening.
5. Keep IPH `weobjectid` as a later single-case capability unless broader platform/protocol evidence appears.
6. Continue deterministic hardening until no reasonable bounded generic class remains.
7. Materialize stable recipes and update the `36/65` numerator only from unchanged strict E2E proof.
8. Only exhausted residuals may enter booster engineering; productive decision order remains deterministic -> ML -> booster.

## Retention / DRJ

ACTIVE / KEEP:

- issue `#676`;
- current `main`;
- `POST-MIGRATION-RESTART.json`;
- issue `#704` and `docs/knowledge/branch_salvage_704.md`;
- this re-entry MD/JSON and target;
- V1-V6 builder/audit chain;
- V6 provider public-feed implementation and tests;
- merged Origin V2, Workday and portal implementations;
- builder residual-rewrite contract.

PRESERVE provenance includes the migration checkpoints, the measured #676 comments, PR histories, and remote branch history until separately authorized retention effects occur.

Remote branch cleanup is not a prerequisite for the project restart PASS. Age, path, name, merge status or repository pressure are never deletion authority. DRJ remains a retention/reconciliation mechanism, not general project work-admission authority.
