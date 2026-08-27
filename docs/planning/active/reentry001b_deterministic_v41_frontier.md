# REENTRY-001B Job Application Pipeline — Deterministic Residual Cluster Frontier

Status: current continuation point for the active deterministic residual-cluster campaign on `agent/672-residual-cluster-frontier` / draft PR `#673`  
Date: 2026-08-27  
Repository: `jenshaberle-dotcom/job-application-pipeline`  
Repository ID: `1230805345`  
Canonical main at this refresh: `4cdcc20c4338db4cda1135c5ca9f16856ab4cd8e`  
Runtime repository: `jenshaberle-dotcom/job-pipeline-runtime`  
Runtime main at this refresh: `b43c99fb1c4ac88bb5cb9419bd654aa4a6df9036`  
Runtime control issue: `#203`  
Active Pipeline frontier issue: `#672`  
Draft implementation PR: `#673`  
Boundary: repository plus persisted/runtime/live bounded evidence are project truth; chat and assistant memory are not project truth

## Purpose and supersession

This file is the canonical continuation point after REENTRY-001A. The old V41/V42
conclusion that acquisition was globally deterministic-exhausted is superseded.

The corrected statement is:

- V7-V42 exhausted the **then-instrumented / persisted evidence surfaces** for the
  bound 40-case acquisition cohort;
- that did **not** prove that all reusable deterministic acquisition classes had been
  tried;
- cluster-first current-surface diagnostics on the seven residuals have since produced
  two strict deterministic rescue proofs and multiple additional generic hypotheses.

Therefore the historical `33/40` is not a deterministic ceiling. It is the canonical
accumulated strict baseline before the current #672 residual-cluster campaign.

## Current canonical repository truth

Pipeline main is `4cdcc20c4338db4cda1135c5ca9f16856ab4cd8e`.

The delta after the previous re-entry refresh is DRJ-only (`PROJECT-DRJ.json` plus the
DRJ reconcile-request mailbox) and does not change acquisition, lifecycle, proof,
Product, source or application semantics.

Main already contains:

- recurring exact-detail lifecycle hardening from `#502/#668`;
- verified-complete-inventory lifecycle hardening from `#669/#670`;
- generic runtime URL aliases `applylink` / `externallink` from `#664/#667`, with no
  proof or host-authority widening;
- the current DRJ semantic/reconcile/actions contract.

Lifecycle negative authority remains split deliberately:

1. **Exact detail:** historical Employer-Origin target identity + historical
   Employer-Origin source typing + bounded exact-detail evidence.
2. **Verified complete inventory:** independently reviewed current complete-inventory
   authority + immutable target identity, allowing `not_seen/complete_inventory`.

Do not conflate lifecycle complete-inventory authority with the acquisition inventory
work described below.

## Acquisition counters — keep the truths separate

Two historical controls remain separate:

1. **Static default acquisition control:** `23/40` genuine-job proven.
2. **Accumulated bounded Runtime deterministic acquisition before #672:** `33/40`
   strict proven, `7/40` unresolved.

Do not add them together.

Historical V40 binding: Runtime run `32977904600`.

Historical residual IDs:

- `33` — `x1f`;
- `45` — `bridgingit`;
- `47` — `commercetools`;
- `48` — `freenet_dls`;
- `52` — `prodyna`;
- `63` — `the_associated_engineers`;
- `72` — `bjak`.

Correct historical label:

`33/40 — V42 evidence-surface exhausted`

Incorrect label:

`33/40 — deterministic acquisition exhausted`

### Current #672 evidence truth

Two residuals now have complete strict deterministic live proof chains:

- `47 / commercetools`;
- `72 / bjak`.

Therefore:

- **canonical accumulated count on main/control:** still `33/40` until promoted code is
  merged and canonical control evidence is rerun;
- **strict evidence-proven frontier:** `35/40`;
- **evidence-proven residual set:** effectively five cases remain to harden/test:
  `33,45,48,52,63`.

Do not credit `35/40` as the canonical accumulated control before the promoted classes
are merged and exercised through the canonical campaign/control path.

## Why acquisition reopened after V42

Fresh current-surface diagnostics showed that the seven residuals were not seven
company-specific exceptions. They cluster into reusable technical families:

- career-origin / provider drift;
- explicit employer-backed delegation;
- provider configuration embedded in first-party code;
- server-rendered or form/pagination inventory;
- client-side/hydrated inventory;
- employer-owned client code explicitly delegating a job API host;
- structured runtime inventory delegating a concrete ATS/detail host.

Campaign principle:

> every deterministic rescue counts twice: once for the current employer and once as
> a reusable precedent for future employers.

`40/40` is desirable if evidence supports it, but it is not an acceptance criterion.

## 47 / commercetools — strict deterministic Greenhouse rescue

Employer origin:

`https://commercetools.com/careers`

The authorized first-party careers code exposes:

- one static board binding: `BOARD = 'commercetools'`;
- the canonical Greenhouse board/jobs template consuming that binding;
- the public Greenhouse metadata endpoint;
- the public Greenhouse jobs endpoint.

Bounded live proof observed:

1. employer careers page — HTTP 200;
2. `https://boards-api.greenhouse.io/v1/boards/commercetools` — HTTP 200;
3. existing `greenhouse_metadata_matches_employer(...)` — `True`;
4. jobs inventory — HTTP 200, `25` jobs;
5. existing strict Greenhouse detail extraction emitted canonical detail URLs;
6. first tested detail — HTTP 200;
7. title: `Job Application for AI Engineer at commercetools`;
8. existing final proof: `job_url_and_job_content`.

Diagnostic result:

`STRICT_COMMERCETOOLS_RESCUE_PROVEN`

The promoted implementation on PR `#673` is generic:

- a uniquely observed static JavaScript variable may provide the Greenhouse board token
  only when the same authorized page also contains the canonical Greenhouse board/jobs
  template consuming that variable;
- multiple/ambiguous/static-without-template/dynamic values fail closed;
- existing metadata employer-identity validation remains mandatory;
- existing jobs payload detail extraction remains mandatory;
- existing final genuine-job proof remains unchanged;
- there is no `commercetools` success branch.

Validation on PR #673 before this re-entry update:

- targeted Greenhouse/V4 regression set: `22 passed`;
- Ruff: passed;
- bounded live V4 replay: `STRICT_COMMERCETOOLS_RESCUE=PASSED`;
- Pipeline CI on code head `e142b44bddc5d3379987db375fe6f12d1da39955`: success;
- re-entry target identity: success.

## 72 / bjak — strict deterministic client-code/API rescue

Employer origin:

`https://bjak.my/en/career`

Existing V4 already reaches the authorized same-host jobs route:

`https://bjak.my/en/career/jobs`

The jobs page is Next.js and explicitly embeds one jobs-specific route chunk:

`/_next/static/chunks/pages/career/jobs-726390e3fc7fd74b.js`

### Client-code delegation evidence

The jobs-specific chunk explicitly contains:

- `GET /career/api-v1/get-all-jobs`;
- base expression `(0,b.S)()`;
- import binding `b=t(63016)`.

The already-embedded same-host `_app` chunk contains the exact module definition:

```text
63016:(e,t,r)=>{"use strict";r.d(t,{S:()=>n});let n=()=>"https://be.bjak.my"}
```

Therefore the exact observed request binding is:

`GET https://be.bjak.my/career/api-v1/get-all-jobs`

This is stronger than host/subdomain inference: method, relative path, imported module,
export and literal HTTPS base are all linked by employer-owned client code.

### Runtime inventory/detail evidence

One bounded GET to that exact observed endpoint returned:

- HTTP 200;
- `application/json`;
- ~1.57 MB response;
- generic runtime recognition: `250` bounded candidates;
- all sampled/recognized candidate URLs on `jobs.ashbyhq.com`;
- under the historical host authority: runtime proofs `0`;
- under diagnostic-only explicit client-code API-host delegation: runtime proofs `250`.

First proven record:

- title: `3D Animator`;
- stable UUID identity;
- detail URL emitted by the inventory:
  `https://jobs.ashbyhq.com/bjakcareer/<uuid>`;
- runtime proof: `runtime_authorized_inventory_record`;
- delegated detail host: `jobs.ashbyhq.com`;
- detail HTTP 200;
- title: `3D Animator @ Bjak`;
- existing final detail proof: `jsonld_jobposting`.

Diagnostic result:

`STRICT_BJAK_RESCUE_PROVEN`

No raw API body was persisted. No DB/Product/source/application writes occurred.

### Promoted Pipeline pure class

PR `#673` now contains a generic pure evidence primitive for this reusable shape:

`authorized page`
→ `same-host JavaScript route chunk`
→ explicit `.get(${importedExport()}<job-context relative path>)`
→ uniquely resolved Webpack module import
→ uniquely resolved export
→ literal HTTPS API base.

Hard fail-closed boundaries include:

- GET-only for this first promoted class;
- route script must be HTTPS and exact same host as the page;
- module script evidence must also be HTTPS and exact same host;
- endpoint path must be relative, queryless and job-contextual;
- POST does not qualify;
- dynamic base expressions do not qualify;
- cross-host scripts do not qualify;
- ambiguous module bindings do not qualify;
- competing module/base definitions do not qualify;
- recognition alone does not authorize an untrusted page.

This primitive performs no network I/O and does not change
`runtime_job_record_proof(...)`.

## 48 / freenet_dls — explicit delegation + server-side inventory frontier

Employer origin:

`https://www.freenet.ag/karriere`

Existing V4 follows the employer-explicit `Jobs` delegation to:

`https://karriere.freenet-group.de`

That listing surface is HTTP 200 and exposes:

- a server-rendered result surface;
- a POST search form;
- pagination;
- many job-like labels.

Current classifier does not recover a concrete detail page. The missing deterministic
class is after already-proven employer delegation:

`authorized listing/inventory -> concrete detail identity`.

Do not reconstruct unknown POST bodies. Prefer explicit pagination/detail/form evidence
already present in the public page.

## 33 / x1f — stale-origin / rediscovery frontier

Persisted origin remains the historical Personio surface:

`https://x1f.jobs.personio.de/`

That route is reachable but no longer yields a useful inventory. Current public
evidence indicates a changed first-party career/provider path.

Generic hypothesis:

`stale known origin -> current employer-backed career rediscovery -> provider fingerprint/delegation -> existing V4 acquisition`.

No generated hostname, tenant or provider route is authority on its own.

## 52 / prodyna — dedicated portal / provider-family frontier

Persisted origin:

`https://jobs.prodyna.com/`

HTTP 200; dedicated job portal; POST form; Umantis-related asset/context observed, but
no currently authorized canonical provider route or concrete detail extraction.

Provider knowledge may shape a parser but may not independently establish employer
or target authority. Next evidence must come from observed routes/forms/scripts/config.

## 45 / bridgingit — thin current surface

Persisted origin:

`https://www.bridging-it.com/de/karriere`

HTTP 200, but the static surface exposed no useful anchors/provider route under the
current parser. Historical Personio assumptions are not sufficient current authority.

Still eligible for current employer-backed delegation / rendered-surface / provider
rediscovery hypotheses.

## 63 / the_associated_engineers — sparsest residual

Persisted origin:

`https://www.associated-engineers.com/careers`

HTTP 200 but very sparse static content. Current first-party deterministic evidence is
not yet enough for a concrete job proof. Marketplace/delegation or current-origin
rediscovery remains a hypothesis, not authority.

## Existing reusable primitives worth preserving

Pipeline already contains:

- canonical ATS provider registry including Greenhouse, Personio, Workday,
  SuccessFactors, SmartRecruiters, Lever, Ashby, Recruitee, Workable, Softgarden,
  d.vinci, Onlyfy, Join, Talention, Umantis and others;
- strict d.vinci provider-detail routing;
- Greenhouse metadata employer-identity validation;
- Greenhouse jobs inventory/detail extraction;
- explicit employer-root job-host delegation;
- V4 bounded provider/listing navigation;
- generic runtime structured-job recognition;
- runtime job-record proof separated from Product authority;
- runtime delegated candidate-host proof;
- final static genuine-job/content proof;
- the new pure explicit client-code GET API delegation recognizer on PR #673.

Prefer composition of these primitives over employer-specific connectors.

## Active deterministic campaign — #672

Campaign order:

1. preserve historical canonical `33/40` until canonical promoted evidence says
   otherwise;
2. cluster residuals by current observed structure/provider behavior;
3. rank by reusable cross-employer value;
4. perform bounded read-only diagnostics first;
5. promote only generic evidence-backed classes;
6. add fail-closed regressions;
7. run canonical control after meaningful promotion;
8. re-cluster remaining residuals;
9. declare deterministic acquisition exhausted only when no remaining evidence supports
   another bounded generic class.

`No rescue` alone is not closure. Closure requires an explicit inventory of attempted
reusable hypotheses and stop reasons.

## Hard boundaries

- no company-specific success branch merely to increase recall;
- no guessed ATS tenant/token/endpoint/selector/job ID;
- no reconstruction of unknown POST bodies or query values;
- no generic click/scroll broadening without a bounded observed class;
- no registrable-domain/subdomain inference as authority;
- no URL-less final job proof;
- no weakening of genuine-job/content proof;
- provider recognition/field names alone are not authority;
- raw HTML/API/XML/JSON bodies, headers, cookies, tokens and request bodies are not
  persisted;
- no DB/Product/source/application mutation in acquisition shadow work;
- ambiguous evidence fails closed;
- technical failed runs are non-evidence.

## Deterministic / booster / ML sequencing

Development order remains:

```text
deterministic hardening -> LLM booster engineering -> ML algorithm engineering
```

Productive decision order remains:

```text
deterministic -> ML algorithm -> booster
```

For acquisition, booster admission remains deferred while #672 continues producing
new reusable deterministic evidence.

Matching/ranking product semantics remain PRD/product-intent gated.

## Deferred deterministic work

`#671` — StepStone wave-cycle preview must become truly read-only — remains valid and
is deferred behind the active acquisition residual campaign.

`#522` — LLM booster — remains valid, but residual acquisition admission is deferred
until #672 reaches evidence-backed exhaustion.

## Required reads for handoff

1. this file;
2. Pipeline issue `#672`;
3. Pipeline draft PR `#673`;
4. Runtime issue `jenshaberle-dotcom/job-pipeline-runtime#203` for V37-V42 history;
5. `src/connectors/employer_origin_acquisition_v4.py`;
6. `src/connectors/employer_origin_greenhouse_navigation.py`;
7. `src/search_intelligence/runtime_network_acquisition.py`;
8. `src/search_intelligence/client_code_api_delegation.py`;
9. `src/search_intelligence/origin_source_discovery_agent.py`;
10. provider/delegation registry modules as needed.

## Sole next safe action

**Canonicalize the already-green Pipeline pure hardening from PR #673, then wire the
new client-code API-host evidence into the Runtime browser adapter without changing
`runtime_job_record_proof(...)`.**

Runtime acceptance for the Bjak precedent:

1. begin only from an already-authorized employer jobs page;
2. inspect only explicitly embedded same-host JavaScript scripts under a hard cap;
3. use `explicit_client_code_api_get_delegation(...)` to resolve the API endpoint;
4. use `client_code_delegated_response_host(...)` only with the existing authorized
   page-host set;
5. add only that exact resolved host to the response-host set for the exact page;
6. call only the exact observed GET endpoint;
7. feed the transient JSON into existing `recognize_job_payload(...)`;
8. require existing `runtime_job_record_proof(...)` before candidate-host delegation;
9. require existing `runtime_delegated_candidate_host(...)` before detail follow-up;
10. require unchanged `genuine_job_detail_proof(...)` on the concrete detail page;
11. persist no raw script/API bodies or query/header/cookie/token values;
12. no Product/source/application/database writes;
13. prove generic negative fixtures and bounded Bjak live replay;
14. after merge, run a canonical 40-case control and update the canonical accumulated
    count only from that evidence.

After Bjak is canonically promoted, continue #672 with Freenet first, then x1F /
PRODYNA / bridgingIT / Associated Engineers according to evidence reuse value.
