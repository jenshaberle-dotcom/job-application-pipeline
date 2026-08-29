# ACQ-GENERALIZATION-90 — canonical re-entry

Status: **ACTIVE — V5 LIVE REPLAY + RESIDUAL RECLUSTER COMPLETE; SUCCESSFACTORS CARRIER AUDIT NEXT**  
Owner issue: `#676`  
Migration delivery merge: `6af34cb54a9bbf29ffc257d1109f495d08d1678d`  
Builder V5 merge: `45f99c1919e6869451b6301bf41a6d3d12ba7c78`  
Latest qualified diagnostic merge: `2b37c89ecf1d4821e4c82f703780138af8744367`

Machine-readable companion: `docs/planning/active/acq_generalization_90_reentry.json`.

## Authority

This file is the active ACQ-676 continuation anchor. It is subordinate to
`PROJECT-HYGIENE.json`, `PROJECT-LOCAL-WORKSPACE.json`, `PROJECT-DRJ.json`, and the
product/current-truth surfaces.

Repository truth, live bounded evidence, tests and CI override chat summaries.
Every new mutating ACQ-676 slice starts from freshly observed current `origin/main`
in a declared worktree/feature branch. Historical #676 branches are never
continuation authority.

## Canonical product metric

Current strict functioning deterministic product coverage remains:

`36 / 65 = 55.4%`

Target at the current denominator:

`>= 59 / 65 = 90.8%`

The historical `36/40` remains a regression cohort. Builder `recipe_ready`, audit
READY states, provider recognition and live diagnostic rescue evidence do not change
the product numerator. A candidate enters the numerator only after a materialized
connector passes unchanged strict E2E acquisition proof under existing authority and
side-effect boundaries.

## Migration / architecture closure

The 2026-08-28 canonical workspace migration is complete. Qualified #676 content was
harvested without importing superseded branch ancestry and delivered through PR
`#682` at merge `6af34cb54a9bbf29ffc257d1109f495d08d1678d`.

The historical migration checkpoint remains preserved provenance:

- `docs/planning/active/acq_generalization_90_migration_checkpoint_20260828.md`;
- `docs/planning/active/acq_generalization_90_migration_checkpoint_20260828.json`.

Builder V5 was merged through PR `#685` at
`45f99c1919e6869451b6301bf41a6d3d12ba7c78` with Pipeline CI `#887` and Re-entry
`#1454` successful. The shared `rewrite_residual_suffix()` contract remains the
mandatory monotonic composition boundary: an adapter may rewrite only the exact
residual it claims, must declare the earliest changed layer, preserves all earlier
layers exactly, and may never move failure earlier.

Current ordered diagnostic composition remains:

```text
V3 base
  -> Workday CXS residual adapter
  -> evidence-bounded portal-delegation residual adapter
  -> remaining residuals
```

## Qualified live V5 replay — 2026-08-29

The canonical WSL replay completed on
`main@05f6a137beb34abfb7cc53669c70c3792a7901e3` via module execution.

Exact transition:

- V3 READY: `21/65`;
- V4 READY: `22/65`;
- V5 READY: `22/65`;
- Workday promotions: `1` -> `clarios_germany`;
- portal promotions: `0`;
- cohort total: `65`;
- earlier-stage regressions: `0`.

Final V5 first-failure population:

- READY: `22`;
- origin: `8`;
- origin_reachability: `1`;
- inventory: `15`;
- detail: `16`;
- proof: `3`.

Exact residual cohorts:

- origin: `computer_futures, hahne_holding, haystack, jobbird_com, limango, sport_alliance, team_passerelle, windhoff`;
- origin_reachability: `deutsche_bahn`;
- inventory: `adesso, adonya_software_services, bahlsen, bridgingit, hannover_ruck, hired, intersport_digital, ivv, kkh_kaufmannische_krankenkasse, nortal, prodyna, sva_system_vertrieb_alexander, technische_informationsbibliothek_tib, the_associated_engineers, trustyou`;
- detail: `1_1, amadeus_fire, aok_niedersachsen_die_gesundheitskasse, bjak, compugroup_medical, deloitte, genoverband_e_v, iph_institut_fur_integrierte_produktion_hannover_ggmbh, land_niedersachsen, msg_systems, mtu_maintenance, triology, tuv_sud, x1f, yer_deutschland, zscaler_germany`;
- proof: `enercity, hdi, ratbacher`.

Durable issue checkpoint: `#676` comment `5462507864`.

Interpretation: Workday has measured generic live lift. Portal delegation has no
measured V5 population lift and must not be widened further from this evidence alone.
Product coverage remains `36/65`.

## Qualified residual re-cluster

The V5 artifact was re-clustered with bounded read-only surface and bridge audits.

Inventory surface audit:

- input inventory residuals: `15`;
- HTTP GETs: exactly `15` (`1` per residual maximum);
- authorized provider without executable inventory: `2` -> `adesso`, `hannover_ruck`;
- client-rendered/script primary: `1` -> `bahlsen`;
- external jobish anchor not promoted: `2` -> `nortal`, `sva_system_vertrieb_alexander`;
- same-origin jobish anchor not classified: `3` -> `kkh_kaufmannische_krankenkasse`, `prodyna`, `trustyou`;
- low-signal inventory surface: `7`.

Bridge audit:

- evidence-rich cases: `7`;
- HTTP GETs: exactly `7`;
- same-origin listing-vocabulary hypothesis: `6`;
- external listing-vocabulary hypothesis: `4`;
- provider-route-adapter gap: `2` -> `adesso`, `hannover_ruck`.

The vocabulary counts include visible navigation noise and are not implementation
priority by count alone. The strongest bounded cross-employer class is the pair of
already-authorized SuccessFactors surfaces with no executable provider inventory
route.

Durable issue checkpoint: `#676` comment `5462664378`.

## SuccessFactors carrier frontier

Focused root observation established:

- `hannover_ruck`: authorized SuccessFactors root, explicit same-host GET form to
  `/search/`, same-host `/platform/js/search/search.js`, `careerSiteCompanyId`;
- `adesso`: authorized SuccessFactors root, no root form, but the same explicit
  same-host `/platform/js/search/search.js` stack and `careerSiteCompanyId`.

This does **not** authorize `/search/` for adesso and does not establish a universal
SuccessFactors inventory route. Public adesso detail URLs also show a `/job-invite/<id>/`
family, while Hannover Re uses `/job/<slug>/<numeric-id>/`; those shapes are evidence
of concrete public details, not inventory enumeration authority.

PR `#688` therefore added only a reusable read-only measurement tool:

- `scripts/run_deterministic_successfactors_search_carrier_audit.py`;
- `tests/test_deterministic_successfactors_search_carrier_audit.py`.

Qualified PR #688 evidence:

- code head: `4b616cf24dbdd3ecdaae97fe0bdd9dabbb15f7d9`;
- Pipeline CI `#896`: success;
- Re-entry `#1479`: success;
- merge: `2b37c89ecf1d4821e4c82f703780138af8744367`.

Audit boundary:

- selects only V5 `inventory` residuals whose surface audit already recognized
  `successfactors`;
- max `2` GETs per eligible candidate: authorized root plus exactly one explicitly
  embedded same-host `/platform/js/search/search.js`;
- no guessed routes, tenants, IDs, POST bodies or query values;
- query values are never persisted; only URL shape/query-key names may be emitted;
- cross-host or ambiguous script evidence fails closed;
- POST evidence cannot be promoted as GET evidence;
- provider/LLM/Tavily requests `0`;
- DB/source/Bronze/Silver/Product/application writes `0`;
- connector materialization `0`.

## Canonical commands

V5 replay from repository root:

```bash
.venv/bin/python -m scripts.run_deterministic_connector_builder_layer_audit_v5 \
  --output /tmp/deterministic_connector_builder_layer_audit_v5.json
```

Current SuccessFactors carrier gate, reusing the qualified V5 and inventory-surface
artifacts:

```bash
.venv/bin/python -m scripts.run_deterministic_successfactors_search_carrier_audit \
  --layer-audit /tmp/deterministic_connector_builder_layer_audit_v5.json \
  --surface-audit /tmp/deterministic_inventory_surface_audit_v5.json \
  --output /tmp/deterministic_successfactors_search_carrier_audit.json
```

Module execution from the repository root is canonical for scripts importing
`scripts.*` / `src.*`; direct-file invocation is not continuation authority.

## Sole continuation sequence

1. Fast-forward the canonical WSL checkout to current `origin/main` and verify clean
   `main` identity.
2. Run the canonical SuccessFactors carrier audit above against the existing qualified
   V5 + inventory-surface artifacts.
3. Record exact evidence for both eligible cases. Do not infer a route that is not
   explicitly bound by root/script evidence and do not change product coverage.
4. If both cases expose a reusable bounded carrier under the same generic contract,
   implement that capability on a fresh branch with unchanged proof/authority.
5. If the carrier class splits or fails closed, record the stop reason and select the
   next evidence-backed residual class by population lift + evidence strength +
   boundedness.
6. Continue deterministic hardening until no reasonable generic deterministic class
   remains.
7. Materialize only stable evidence-backed recipes and update the product numerator
   only from unchanged strict E2E proof; only exhausted residuals may then enter the
   booster path.

## Retention / DRJ semantic dispositions

### ACTIVE / KEEP

- issue `#676`;
- current `main`;
- this re-entry MD/JSON and `acq_generalization_90_target.md`;
- V1-V5 builder audits and focused tests;
- inventory surface/bridge audits;
- SuccessFactors search-carrier audit + focused tests;
- merged Origin V2, Workday and portal-delegation implementations;
- deterministic builder residual-rewrite contract.

### PRESERVE — provenance

- migration checkpoint MD/JSON;
- issue `#676` comments `5462507864` and `5462664378`;
- PR histories `#682`, `#685`, `#687`, `#688` and their qualified gate evidence.

### SUPERSEDED / no continuation authority

- PR `#678` / `agent/676-deterministic-connector-builder`;
- PR `#682` / `agent/676-generalization-harvest` after merge;
- Draft PR `#684`;
- PR `#685` / its merged branch after delivery;
- PR `#687` / its merged branch after delivery;
- PR `#688` / `agent/676-successfactors-search-carrier-audit` after delivery.

Branch/worktree deletion is still a separate DRJ technical effect requiring fresh
local observation. Age, path or branch name are never deletion authority.

`DRJ-RECONCILE-REQUEST.json` remains `NO_REQUEST` unless fresh local hygiene evidence
identifies an exact technically safe retirement set. DRJ is retention/reconciliation
infrastructure, not ACQ-676 work-admission authority.

## Re-entry commandment

Before mutating ACQ-676, read in order:

1. `PROJECT-HYGIENE.json`;
2. `PROJECT-LOCAL-WORKSPACE.json`;
3. `PROJECT-DRJ.json`;
4. `docs/current/README.md`;
5. this file;
6. `acq_generalization_90_target.md`;
7. live issue `#676` and current PR state;
8. current `origin/main`, branch/worktree relationship and latest CI.

Do not resume from historical #676 branches or chat memory.
