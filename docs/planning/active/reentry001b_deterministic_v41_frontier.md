# REENTRY-001B Job Application Pipeline — Deterministic Residual Cluster Frontier

Status: current canonical continuation point on branch `agent/672-residual-cluster-frontier`; V41/V42 acquisition surface closed, cluster-first residual campaign active  
Date: 2026-08-27  
Repository: `jenshaberle-dotcom/job-application-pipeline`  
Repository ID: `1230805345`  
Canonical main at refresh: `babbb6789659b012f4cc55bb197a7de0f19e318f`  
Runtime repository: `jenshaberle-dotcom/job-pipeline-runtime`  
Runtime main: `96f0fbf4f0cecf5764fb053c4b3b0a572ea6634f`  
Runtime control issue: `#203`  
Active Pipeline frontier issue: `#672`  
Boundary: repository plus persisted/runtime/live bounded evidence are project truth; chat and assistant memory are not project truth

## Purpose and supersession

This file remains the canonical continuation point after REENTRY-001A, but the old
V41-specific next action is stale and is superseded by the current residual-cluster
campaign.

The important correction is semantic:

- V7-V42 exhausted the **then-instrumented evidence surfaces** for the bound 40-case
  acquisition cohort;
- that did **not** prove deterministic acquisition itself was globally exhausted;
- fresh cluster-oriented diagnostics on the seven residuals have now produced new
  reusable deterministic hypotheses and one strict live rescue proof.

Therefore `33/40` must no longer be described as the deterministic ceiling. It is the
historical accumulated strict baseline before the current residual-cluster campaign.

## Current canonical repository truth

Main is `babbb6789659b012f4cc55bb197a7de0f19e318f`.

That main already contains:

- the completed recurring exact-detail lifecycle hardening from `#502/#668`;
- the completed verified-complete-inventory lifecycle hardening from `#669/#670`;
- `PROJECT-DRJ.json` as the current DRJ semantic/reconcile/actions contract.

The lifecycle layer now supports two distinct deterministic negative-authority paths:

1. **Exact detail:** historical employer-origin target identity plus historical
   employer-origin source typing plus exact-detail evidence.
2. **Verified complete inventory:** independently proven current source-level
   complete-inventory authority plus immutable target identity, allowing
   `not_seen/complete_inventory` without pretending legacy Bronze source typing was
   rewritten.

Both paths remain fail-closed and preserve the no-product-authority boundary.

## Acquisition control truth

Two historical controls remain intentionally separate:

1. **Static default acquisition control: `23/40` genuine-job proven.**
2. **Accumulated bounded Runtime deterministic acquisition before the residual-cluster
   campaign: `33/40` strict proven, `7/40` unresolved.**

Do not add these values together.

The historical authoritative accumulated Runtime binding remains V40 run
`32977904600`, with residual IDs:

- `33` — `x1f`;
- `45` — `bridgingit`;
- `47` — `commercetools`;
- `48` — `freenet_dls`;
- `52` — `prodyna`;
- `63` — `the_associated_engineers`;
- `72` — `bjak`.

V41/V42 and the post-V42 audit established that no further reusable class was open in
the **already-persisted evidence under the then-instrumented surfaces**. The correct
label for that result is:

`33/40 — V42 evidence-surface exhausted`

It is **not**:

`33/40 — deterministic acquisition exhausted`.

## Why acquisition reopened after V42

A fresh residual-cluster review tested current public employer-backed surfaces rather
than treating each unresolved case as an isolated exception.

The seven residuals now show multiple reusable technical families:

- stale/changed career origin or ATS/provider drift;
- explicit employer-backed delegation to a dedicated job portal;
- first-party paginated/server-rendered inventory;
- hydrated/client-side inventory with observed API routes;
- embedded provider configuration that can deterministically bind an ATS tenant/board.

The campaign objective is therefore not to force `40/40`. It is to exhaust every
reasonable reusable deterministic hypothesis before admitting a residual to the LLM
booster. Every accepted rescue must become a generic precedent with regression
coverage.

## Residual cluster evidence — current state

### 33 / x1f — stale-origin / rediscovery candidate

Persisted origin remains:

`https://x1f.jobs.personio.de/`

A bounded current-root probe still reaches that Personio surface, but it yields no job
navigation. Provider-free origin rediscovery independently selects the x1F first-party
career family (`www.x1f.de/karriere` candidates) rather than the stored Personio route.

Current interpretation:

- the persisted origin is stale or no longer sufficient for acquisition;
- x1F belongs to a reusable **career-origin rediscovery / provider-drift** class;
- no new product or employer authority has yet been granted;
- rediscovery must be proved from employer identity + career evidence, not host-only
  inference or guessed ATS tenants.

### 45 / bridgingit — thin employer-origin / delegated ATS candidate

Persisted origin:

`https://www.bridging-it.com/de/karriere`

Current bounded GET returns HTTP 200 but only a tiny HTML surface and no usable anchors,
provider fingerprint, forms, embedded detail URLs or current classifier candidates.

Current interpretation:

- not an HTTP failure;
- likely requires a current employer-backed delegation/rediscovery class or a rendered
  surface diagnostic;
- no provider-specific success rule is authorized yet.

### 47 / commercetools — strict Greenhouse rescue proof established

Persisted/current employer origin:

`https://commercetools.com/careers`

The first-party careers HTML now supplies a complete deterministic Greenhouse chain:

- unique observed static board token: `commercetools`;
- canonical Greenhouse jobs URL template observed in the same first-party code;
- derived metadata URL:
  `https://boards-api.greenhouse.io/v1/boards/commercetools`;
- metadata HTTP 200;
- existing `greenhouse_metadata_matches_employer(...)` returns `True`;
- metadata board name is exactly `commercetools`;
- observed jobs endpoint returns HTTP 200 with `25` jobs;
- existing `greenhouse_detail_urls_from_jobs(...)` returns strict canonical Greenhouse
  detail URLs;
- first tested detail returns HTTP 200;
- title: `Job Application for AI Engineer at commercetools`;
- existing `genuine_job_detail_proof(...)` returns
  `job_url_and_job_content`.

Exact bounded request chain:

```text
1. commercetools first-party careers page
2. Greenhouse board metadata
3. Greenhouse board jobs inventory
4. concrete Greenhouse detail URL
```

Diagnostic result:

`STRICT_COMMERCETOOLS_RESCUE_PROVEN`

This is a real strict deterministic rescue proof under the existing final proof
boundary. It is **not yet credited to the canonical accumulated control**, because the
generic parser extension has not yet been merged and the full control has not been
rerun.

The authorized reusable implementation candidate is narrow:

> accept a uniquely observed static Greenhouse board token only when the same already-
> authorized first-party page also contains the canonical Greenhouse board/jobs URL
> template that consumes that token; then retain the existing metadata employer-
> identity check, jobs-payload detail extraction and final genuine-job proof.

No `commercetools` company branch is allowed.

### 48 / freenet_dls — explicit delegation + server-side inventory frontier

Employer origin:

`https://www.freenet.ag/karriere`

The root explicitly delegates the `Jobs` link to:

`https://karriere.freenet-group.de`

Existing V4 acquisition follows this delegation successfully. The delegated surface is
HTTP 200, server-rendered, has a POST search form, pagination links and many job-like
labels, but the current detail classifier emits only false-positive career-information
links and no genuine job detail candidate.

Current interpretation:

- employer-origin -> delegated listing authority is already proven;
- the missing class is **listing/inventory -> concrete detail extraction**;
- likely reusable server-rendered pagination/form inventory class;
- no guessed POST body or hidden parameter is allowed.

### 52 / prodyna — dedicated portal / Umantis-family candidate

Persisted origin:

`https://jobs.prodyna.com/`

The page is HTTP 200, has a POST form and a dedicated job-portal surface. Current parser
logic finds no listing/detail candidate. The HTML contains an Umantis-related workflow
asset/context, but no currently authorized canonical provider route.

Current interpretation:

- dedicated ATS/job-portal family candidate;
- provider knowledge may shape a parser but may not create employer authority;
- next evidence must come from observed routes/forms/scripts/configuration rather than
  guessed Umantis endpoints.

### 63 / the_associated_engineers — sparse surface

Persisted origin:

`https://www.associated-engineers.com/careers`

Current bounded GET is HTTP 200 but returns only a tiny HTML surface with no anchors,
forms, provider fingerprints, embedded URLs or job detail evidence.

Current interpretation:

- still the sparsest residual;
- likely requires current origin/delegation rediscovery or a rendered/marketplace
  boundary diagnostic;
- no deterministic class is yet proven for this case.

### 72 / bjak — observed client-code API inventory candidate

Employer origin:

`https://bjak.my/en/career`

Existing V4 follows the explicit same-host jobs route:

`https://bjak.my/en/career/jobs`

The jobs page is Next.js and exposes one unique jobs-specific client chunk:

`/_next/static/chunks/pages/career/jobs-726390e3fc7fd74b.js`

The page's `__NEXT_DATA__` contains no concrete job records, but the explicitly observed
jobs chunk exposes exact current API behavior:

- `GET /career/api-v1/get-all-jobs`;
- `POST /career/api-v1/get-department-list`.

For `get-all-jobs`, the minified client code explicitly performs `.get(...)` and reads
`.data.data`; therefore the method and route are observed evidence, not guessed
semantics.

No API endpoint was called in this diagnostic, and no raw response/query values were
persisted.

Current interpretation:

- Bjak belongs to a reusable **observed client-code API discovery** class;
- the next bounded diagnostic may call only the explicitly observed GET jobs endpoint;
- response structure must still yield a concrete URL or another authority-safe
  list/detail relationship before any strict rescue can be credited;
- prior `applylink` / `externallink` evidence remains useful but cannot widen host
  authority by itself.

## Existing reusable provider/navigation primitives

The repository already contains reusable deterministic provider machinery. Important
current examples:

- canonical ATS provider registry includes Greenhouse, Personio, Workday,
  SuccessFactors, SmartRecruiters, Lever, Ashby, Recruitee, Workable, Softgarden,
  d.vinci, Onlyfy, Join, Talention, Umantis and others;
- d.vinci already has a strict provider-detail route contract;
- Greenhouse already has metadata employer-identity validation, jobs-inventory
  parsing and strict detail URL extraction;
- V4 acquisition already supports one bounded extra hop for high-confidence
  provider/listing/detail evidence;
- explicit employer-root job-host delegation already exists;
- final genuine-job/content proof remains unchanged.

The residual campaign should therefore prefer **composition and narrowly evidenced
parser extensions** over new company-specific connectors.

## Active deterministic campaign — #672

Issue `#672` is the active acquisition frontier.

Campaign order:

1. preserve the historical `33/40` baseline;
2. cluster residuals by shared observed structure/provider behavior;
3. rank hypotheses by expected cross-employer reuse;
4. run offline/read-only bounded diagnostics first;
5. promote only evidence-backed generic classes;
6. protect each promoted class with regressions and unchanged authority boundaries;
7. rerun the full 40-case control after each meaningful merged rescue class;
8. re-cluster remaining residuals;
9. declare deterministic acquisition exhausted only when no remaining evidence supports
   another bounded generic hypothesis.

`40/40` is welcome if evidence supports it, but is not an acceptance criterion.

## Hard boundaries

- no company-specific success branch merely to increase recall;
- no guessed ATS token, tenant, endpoint, selector, route, board, site or job ID;
- no reconstruction of unknown POST bodies or query values;
- no generic click/scroll broadening without a new bounded observed class;
- no registrable-domain inference as host authority;
- no URL-less final job proof;
- no weakening of final genuine-job/content proof;
- provider recognition, field names and structural grouping alone are never Product/job
  authority;
- raw HTML/API/XML/JSON bodies, headers, cookies, tokens and request bodies are not
  persisted;
- no DB/Product/source activation/scheduler/application mutation in acquisition shadow
  work;
- ambiguous evidence fails closed;
- technical failed runs are non-evidence.

## Deterministic / booster / ML sequencing

The current development order remains:

```text
deterministic hardening -> LLM booster engineering -> ML algorithm engineering
```

The productive decision order remains:

```text
deterministic -> ML algorithm -> booster
```

For acquisition, the LLM booster remains deferred because `#672` has already produced
new deterministic evidence beyond V42.

The phrase `ML-first` used in the StepStone discovery lane refers to Machine-Learning-
Engineer search terms, not to the future ML-algorithm layer.

Matching/ranking product semantics remain gated where PRD/product intent is unresolved.

## Deferred but still valid deterministic work

`#671` StepStone wave-cycle plan/read-only hardening remains a valid deterministic
defect, but it is deferred behind the current acquisition residual campaign.

The discovered defect is that the nominal dry-run planning path initializes/persists
cycle state before planning. It should be repaired later so plan/preview is truly
read-only. It is not the current acquisition frontier.

## Required reads for next handoff

1. this file;
2. Pipeline issue `#672`;
3. Runtime issue `jenshaberle-dotcom/job-pipeline-runtime#203` for historical V37-V42
   evidence;
4. `src/connectors/employer_origin_acquisition_v4.py`;
5. `src/connectors/employer_origin_acquisition.py`;
6. `src/connectors/employer_origin_greenhouse_navigation.py`;
7. `src/connectors/employer_origin_ats_navigation.py`;
8. `src/connectors/employer_origin_provider_delegation.py`;
9. `src/search_intelligence/ats_provider_registry.py`;
10. `src/search_intelligence/origin_source_discovery_agent.py`;
11. REENTRY-001A only for historical V37-V39 context.

## Sole next safe action

**Promote the commercetools proof as a generic Greenhouse embedded-board-binding class,
not as a company-specific rule.**

Acceptance for that slice:

1. a first-party already-authorized page must expose exactly one bounded static board
   token;
2. the same page must expose the canonical Greenhouse board/jobs URL template consuming
   that token;
3. ambiguous/multiple/dynamic/non-canonical token evidence fails closed;
4. existing Greenhouse metadata employer-identity validation remains mandatory;
5. existing jobs-payload detail extraction remains mandatory;
6. existing genuine-job/content proof remains mandatory;
7. no host/product/source authority widening;
8. regression tests include positive generic fixture and negative ambiguous/template-
   missing fixtures;
9. bounded live replay reproduces the strict commercetools rescue;
10. after merge, rerun the full 40-case control and update the accumulated strict count
    only from that canonical evidence.

After that class is closed, continue `#672` with the observed Bjak
`GET /career/api-v1/get-all-jobs` diagnostic and then the Freenet/PRODYNA/x1F clusters.
