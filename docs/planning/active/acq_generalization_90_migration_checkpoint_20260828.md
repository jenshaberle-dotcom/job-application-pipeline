# ACQ-GENERALIZATION-90 — migration checkpoint 2026-08-28

Status: **PAUSED FOR CANONICAL WORKSPACE MIGRATION**  
Owner issue: #676  
Draft PR: #678  
Repository: `jenshaberle-dotcom/job-application-pipeline` (`repo_id=1230805345`)  
Source branch at pause: `agent/676-deterministic-connector-builder`  
Code head before checkpoint docs: `f5a3e93ad8f0bed8678db366a221cd2d551236cb`  
Old local workspace: `/home/jens_h/projects/job-application-pipeline`

Machine-readable companion: `docs/planning/active/acq_generalization_90_migration_checkpoint_20260828.json`.

## Why this checkpoint exists

Development is intentionally stopped before moving the repository into a new canonical local workspace. This checkpoint preserves the current evidence frontier so the migrated workspace can resume from repository truth instead of repeating diagnostics or relying on `/tmp` state.

No new acquisition capability should be developed during the migration itself.

## Canonical target and metric

The product target remains:

`strict_functioning_candidates / all_current_distinct_candidates >= 0.90`

Current full population:

- all current distinct candidates: `65`;
- connectors present: `40/65`;
- canonical strict functioning deterministic acquisition: `36/65 = 55.4%`;
- minimum passing numerator at `N=65`: `59/65 = 90.8%`;
- historical 40-case connector cohort remains a non-regression control (`36/40` strict proven within that cohort).

The builder's diagnostic `recipe_ready` value is **not** the canonical product numerator. Product coverage remains `36/65` until a candidate has a materialized connector and unchanged strict E2E acquisition proof.

## Builder architecture fixed during #676

The connector-builder layer order is:

`identity -> origin -> origin_reachability -> delegation -> provider -> inventory -> detail -> proof -> recipe`

Layer necessity is evidence-driven. Optional layers may be `SKIPPED required=false`; they must not create artificial failures merely because a generic stage does not apply.

## Origin generalization result

The original bounded planner was structurally biased toward deep variants of the first host family. The balanced planner now uses evidence-tiered breadth: strong explicit aliases/short brands receive a small bounded fast lane, while enough budget remains for independent host-family breadth.

Observed A/B frontier:

- Origin first-failures: `18 -> 8`;
- prior Origin failures advanced: `10/18`;
- earlier-stage regressions: `0`.

Important regression case repaired: E.ON Digital Technology. The original V1 found `jobs.eon.com`, while the first broad V2 consumed the 12-probe budget on root host variants and regressed E.ON to Origin. The balanced planner restored E.ON while keeping the newly rescued cases.

## Balanced V2 all-65 checkpoint

Diagnostic result before provider-route composition:

- `recipe_ready = 21/65`;
- first failure `origin = 8`;
- `origin_reachability = 1`;
- `inventory = 17`;
- `detail = 15`;
- `proof = 3`.

Fresh out-of-sample ten under balanced V2:

- `READY = 1`;
- `detail = 3`;
- `inventory = 5`;
- `origin = 1`.

The fresh ten are therefore no longer `0/10` at the diagnostic recipe level, but canonical strict connector coverage for those newly created candidates has not been promoted from this diagnostic state.

## Inventory diagnosis preserved

The 17 balanced-V2 Inventory failures were not 17 independent connector types. Read-only surface evidence showed overlapping reusable classes:

- authorized ATS/provider already visible: `4`;
- same-origin job-like carriers: `8`;
- external job-like carriers: `4`;
- client/script evidence: `10`;
- low-signal after one root GET: `7`.

The narrower bridge audit observed:

- `same_origin_listing_vocabulary_gap = 8`;
- `external_listing_vocabulary_gap = 5`;
- `provider_route_adapter_gap = 2`;
- `explicit_canonical_provider_anchor_not_authorized = 1`.

Do **not** globally widen listing vocabulary from the `8` count: the evidence set contains both useful carriers (`Alle Jobs`, `Job Portal`, `Karriere`) and obvious navigation noise (`Skip to main content`, home/password links, mailto-like surfaces).

## V3 provider-inventory composition result

The builder had a layer-composition defect: provider recognition could pass, but `inventory_observed` was derived only from generic navigation and ignored already-existing provider listing/detail adapters.

V3 composes only routes already emitted by the existing authorized provider adapters. It introduces no new provider authority, host authority, request budget, proof rule, DB write, or connector materialization.

All-65 V2 -> V3 result:

- diagnostic `READY: 21/65 -> 21/65`;
- Inventory first-failures: `17 -> 16`;
- Detail first-failures: `15 -> 16`;
- earlier-stage regressions: `0`;
- `x1F: inventory -> detail` through its already-authorized canonical Personio `/xml` route;
- `adesso`, `Clarios`, `Hannover Rück` remained Inventory at V3.

Fresh ten remained:

- ADONYA Software und Services GmbH -> `inventory`;
- Bahlsen Group -> `inventory`;
- INTERSPORT Digital GmbH -> `inventory`;
- IPH -> `detail`;
- KKH -> `inventory`;
- loyos bi -> `READY`;
- MTU Maintenance -> `detail`;
- Nortal -> `inventory`;
- Sport Alliance -> `origin`;
- TRIOLOGY -> `detail`.

### V3 exact first-failure cohorts

Origin (8):
`computer_futures`, `hahne_holding`, `haystack`, `jobbird_com`, `limango`, `sport_alliance`, `team_passerelle`, `windhoff`.

Origin reachability (1):
`deutsche_bahn`.

Inventory (16):
`adesso`, `adonya_software_services`, `bahlsen`, `bridgingit`, `clarios_germany`, `hannover_ruck`, `hired`, `intersport_digital`, `ivv`, `kkh_kaufmannische_krankenkasse`, `nortal`, `prodyna`, `sva_system_vertrieb_alexander`, `technische_informationsbibliothek_tib`, `the_associated_engineers`, `trustyou`.

Detail (16):
`1_1`, `amadeus_fire`, `aok_niedersachsen_die_gesundheitskasse`, `bjak`, `compugroup_medical`, `deloitte`, `genoverband_e_v`, `iph_institut_fur_integrierte_produktion_hannover_ggmbh`, `land_niedersachsen`, `msg_systems`, `mtu_maintenance`, `triology`, `tuv_sud`, `x1f`, `yer_deutschland`, `zscaler_germany`.

Proof (3):
`enercity`, `hdi`, `ratbacher`.

Diagnostic READY (21):
`accompio`, `commercetools`, `computacenter`, `comrce`, `dirk_rossmann`, `e_on_digital_technology`, `e_on_grid_solutions`, `finanz_informatik`, `freenet_dls`, `gft_technologies`, `it_niedersachsen`, `landesbetrieb_it_niedersachsen`, `loyos_bi`, `madsack`, `materna`, `materna_information_communications`, `ratiodata`, `sopra_steria`, `vhv_gruppe`, `wavestone`, `wertgarantie`.

## Recovered Workday precedent

Repository history already contained an unmerged generic Workday implementation on:

- branch: `agent/630-workday-cxs-acquisition`;
- commit: `63a4436ad4aa91d270aef22afd25ca6be2c4cd82`;
- commit message: `Route delegated Workday boards through metered CXS inventory`.

Its strict reusable path is:

`authorized canonical Workday board -> exact /wday/cxs/<tenant>/<site>/jobs POST -> same-board externalPath -> public detail -> unchanged genuine-job proof`

The #676 branch recovered the route module and added a fail-closed employer-backed board bridge. A single Workday control URL is insufficient; multiple distinct explicit canonical control paths must agree on exact host + locale + site (or a visible canonical board route must exist). No tenant/site value is guessed from company identity.

## Latest live evidence: Clarios Workday bridge

This was the final run immediately before the migration pause.

Source code head used:
`f5a3e93ad8f0bed8678db366a221cd2d551236cb`

Focused Workday contract:

- `6 passed`;
- Ruff: all checks passed.

Live decision:

`detail_not_proven`

Reason:

`detail was reached but unchanged strict genuine-job proof did not pass`

Exact evidence-backed route:

- Workday host: `clarios.wd5.myworkdayjobs.com`;
- tenant: `clarios`;
- site: `clarioscareers`;
- locale: `en-US`;
- board: `/en-US/clarioscareers`;
- inventory: `/wday/cxs/clarios/clarioscareers/jobs`.

Request trace, bounded at exactly four requests:

1. `GET jobs.clarios.com/` -> `200`;
2. `GET clarios.wd5.myworkdayjobs.com/en-US/clarioscareers` -> `200`;
3. `POST clarios.wd5.myworkdayjobs.com/wday/cxs/clarios/clarioscareers/jobs` -> `200`;
4. `GET clarios.wd5.myworkdayjobs.com/en-US/clarioscareers/job/Germany-Hannover/Praktikant-Werkstudent--m-w-d--im-Bereich-HR---Talent-Acquisition---Employer-Branding_WD50023-1` -> `200`.

The fourth request proves that the exact CXS inventory produced a concrete same-board public detail URL. The detail page was reachable on the exact authorized canonical Workday host, but the unchanged canonical `genuine_job_detail_proof` returned no proof kind.

Boundary:

- absolute request cap: `4`;
- HTTP requests: `4` (`3 GET`, `1 POST`);
- provider requests: `0`;
- LLM requests: `0`;
- Tavily requests: `0`;
- DB writes: `0`;
- connector materialization: `0`;
- persisted query values: `0`.

### Correct interpretation of Clarios

The live evidence now proves the deterministic chain through **Origin/authority -> Workday board -> CXS inventory -> concrete detail**. The first observed live failing boundary is **strict proof**, not discovery of a listing or detail URL.

However, V3 still formally reports Clarios at `inventory` because this Workday execution path has not yet been integrated into the current builder/acquirer on #676. Do not rewrite historical V3 results and do not count any product coverage lift from the standalone audit.

## CI / repository state at pause

At code head `f5a3e93ad8f0bed8678db366a221cd2d551236cb`:

- Pipeline re-entry run `33174528839`: **success**;
- Pipeline CI run `33174528856`: **success**;
- draft PR #678: open, mergeable, not merged.

The checkpoint documentation itself is intentionally the only work after that green code head.

## Ephemeral local artifacts that may disappear during migration

Their relevant result truth is preserved above and in the companion JSON:

- `/tmp/deterministic_connector_builder_layer_audit_v2_balanced.json`;
- `/tmp/deterministic_connector_builder_layer_audit_v3_provider_inventory.json`;
- `/tmp/deterministic_inventory_surface_audit_balanced.json`;
- `/tmp/deterministic_inventory_bridge_audit.json`;
- `/tmp/deterministic_workday_bridge_clarios.json`.

Do not depend on these paths surviving the workspace migration.

## Hard boundaries to carry into the new workspace

- no company-specific success branches;
- no guessed tenant/opaque IDs/routes;
- no proof weakening;
- no provider/LLM/Tavily requirement for the deterministic target;
- no DB/source/Bronze/Silver/Product writes from diagnostic builder work;
- optional layers are skipped when evidence says they are unnecessary;
- canonical product coverage stays `36/65` until materialized strict E2E proof establishes otherwise;
- target remains at least `59/65` for the current denominator.

## Resume contract after migration

First rebind the **new canonical local workspace** to:

- repository `jenshaberle-dotcom/job-application-pipeline`;
- branch `agent/676-deterministic-connector-builder`;
- issue #676;
- draft PR #678.

Then verify that the remote branch contains this migration checkpoint and re-read this file plus `acq_generalization_90_target.md`. Do not repeat the completed Origin V2, Inventory surface/bridge, provider V3, or Clarios route-discovery work unless repository/network truth has materially changed.

### Sole next engineering action

**Read-only diagnose why the exact Clarios Workday detail page fails the unchanged `genuine_job_detail_proof`. Do not weaken proof.**

From that evidence, decide the smallest generic Workday integration/proof step and then replay the same 65-candidate builder cohort before any connector materialization or coverage promotion.
