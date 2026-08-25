# REENTRY-001A Job Application Pipeline Re-Entry Decision

Status: current repository re-entry; deterministic runtime acquisition hardening active  
Date: 2026-08-25  
Repository: `jenshaberle-dotcom/job-application-pipeline`  
Repository ID: `1230805345`  
Current Pipeline main before this re-entry refresh: `c218a5b827a8189ab0c6e900dee7cb56e8385d30`  
Boundary: repository and Runtime evidence are project truth; chat is not project truth

## Purpose

This file is the canonical continuation point for the Job Application Pipeline.
The previous version was authoritative through V27 at `29/40` strict proven and
`11/40` unresolved. It is stale because two additional deterministic inspections
have since completed:

- V28 tested whether an already-canonical provider detail URL at the observed root
  could reuse existing `known_detail` semantics without changing the genuine-job
  content proof. It produced no rescue.
- V29 replayed only literal, historically persisted ATS listing URLs that were
  still current-authorized and had not already been retried. Candidate `40` /
  Compugroup Medical was rescued through an actual Workday detail GET with the
  unchanged `jsonld_jobposting` proof.

The current measured cohort is therefore **`30/40` strict proven and `10/40`
unresolved**.

Generic visible click/scroll broadening remains evidence-exhausted for this bound
cohort. Deterministic acquisition as a whole is not yet exhausted: the exact
10-case residual still requires an inspection for literal, already-observed
job-related routes on already-authorized hosts across the historical V9/V13
sanitized evidence.

## Required reads

Before continuing from this point, authenticate repository ID `1230805345` and read:

1. this file completely;
2. Pipeline issue `#642` (`ACQ-RUNTIME-001`);
3. `docs/reference/search-intelligence/runtime_network_acquisition.md`;
4. merged Pipeline PRs `#645`, `#646`, `#650`, and `#653`;
5. Runtime repository `jenshaberle-dotcom/job-pipeline-runtime`, issue `#203`;
6. Runtime issue #203 comment `5413405373`, the authoritative V29 checkpoint;
7. Runtime V25 run `32842742734`, V26 run `32859303936`, authoritative V27 retry
   run `32860970408`, V28 run `32865852021`, and authoritative V29 retry run
   `32867166735`;
8. V29 persisted evidence at branch
   `carrier/203-observed-provider-listing-replay-v29-32867166735`, path
   `carriers/connector-observed-provider-listing-replay-v29/32867166735/result.json`;
9. historical V9 endpoint evidence run `32644166249` and V13 static-route evidence
   referenced from Runtime issue `#203`;
10. Pipeline issue `#522` (`LLM-BOOST-001`) and
    `docs/reference/search-intelligence/booster_admission.md`;
11. `docs/planning/active/ml_learning_foundation_lane.md`.

Do not substitute assistant memory, chat summaries, retired NEXT artifacts, stale
planning notes, or superseded PR descriptions for these sources.

## Static V4 control baseline

The fixed static control remains:

- input: `40`;
- strict genuine-job acquisition proven: `23`;
- blocked: `17`;
- blocked reason: `no_genuine_job_detail` for all 17;
- static request contract unchanged: base 3 plus only the existing shared fourth
  request, absolute static cap 4;
- provider/LLM/Tavily requests: `0`;
- Product/DB/source/application mutation: `0`.

Later Runtime campaigns do not rewrite this baseline. They measure incremental
strict rescue against it.

## Current authoritative acquisition truth

Runtime issue #203 comment `5413405373` is the current cohort checkpoint.
Authoritative V29 retry run `32867166735` executed against exact Runtime base
`36b753c61796e416462b521afc3bc9ed09971af7`, exact Pipeline snapshot
`c218a5b827a8189ab0c6e900dee7cb56e8385d30`, authoritative V26 run
`32859303936`, and historical V9 endpoint evidence `32644166249`.

The result chain is:

- V4 static baseline: `23/40`;
- deterministic strict rescues through V24: `+5`;
- V25 visible interaction: `+1` — candidate `37` / E.ON Grid Solutions;
- V26 interaction harness hardening: `+0`;
- V27 Personio public-feed proof: `+0`;
- V28 canonical provider-root detail proof: `+0`;
- V29 observed ATS listing replay: `+1` — candidate `40` / Compugroup Medical;
- **current strict proven: `30/40`**;
- **current unresolved: `10/40`**.

### V28 result

V28 admitted exactly one case/seed: candidate `32` / Genoverband on the observed
canonical d.vinci URL `/de/jobs/118/intro`. The URL returned HTTP `200` and retained
strict d.vinci provider-detail authority, but both the control proof and the
existing `known_detail=True` proof remained null because the unchanged genuine-job
content/title requirements did not hold. V28 therefore added no recall and the
root-detail promotion was not adopted.

### V29 result

V29 replayed only historical ATS-provider URLs that were:

- literal endpoints persisted by V9;
- queryless HTTPS;
- still current-authorized for the exact residual case;
- recognized by the current ATS registry;
- not already present in the current V26 seed set;
- not static assets, login/apply/privacy noise, or non-GET form hints.

Exactly one residual case was eligible: candidate `40` / Compugroup Medical.
Historical Workday listing seeds `/cgm` and `/de-DE/cgm` were opened passively.
The listing page exposed a visible Workday detail URL. A separate metered GET to
that exact discovered URL returned HTTP `200` and passed unchanged
`jsonld_jobposting` proof. V29 therefore added one strict rescue.

V29 also observed real Workday frontend traffic, including a public jobs POST and
job-detail GET under `/wday/cxs/...`. This is observational protocol evidence only;
V29 did not construct or guess a CXS route. No second Workday case remains in the
current 10-case residual, so a Workday-CXS adapter is not the current cohort's
strongest next deterministic slice.

The earlier V29 run `32866803722` is not acquisition evidence. It failed before any
historical ATS page was opened because the isolated Playwright image lacked the
Python `playwright` package. Runtime PR `#313` repaired that transport and retry run
`32867166735` is authoritative.

## Current deterministic authority

The active deterministic runtime contract remains ACQ-RUNTIME-001:

```text
authorized public career/listing page
-> bounded browser observation
-> optional bounded visible listing interaction
-> transient structured response
-> generic runtime payload recognition
-> runtime job-record proof
-> bounded observed inventory/delegated-host authority where proven
-> existing provider-family/public-inventory authority where exact identity is proven
-> unchanged downstream acquisition authority
```

The browser is an evidence sensor. Rendering, clicking, provider recognition, or a
historically observed route alone never grants host, source, job, lifecycle,
ranking, application, or Product authority.

### Visible interaction

Slice 3A remains implemented in
`src/search_intelligence/runtime_listing_interaction.py` with the default per-page
budget:

```text
max_total_actions = 3
max_click_actions = 2
max_scroll_actions = 1
```

V25 proved the slice can add recall. V26 removed generic harness artefacts and then
produced no additional rescue. For this bound cohort, **do not broaden click/scroll
semantics merely to chase recall**.

### Runtime structured-response proof

`src/search_intelligence/runtime_network_acquisition.py` remains authoritative for:

- bounded JSON traversal;
- secret-like query redaction;
- generic job-context recognition;
- explicit non-job-container precedence;
- `runtime_job_record_proof`;
- `runtime_page_delegated_inventory_record`;
- bounded one-hop delegated candidate-host authority after proof.

No raw runtime response is persistent truth.

### Provider/public-inventory evidence

V27 proved the exact current Personio XML feed for X1F is real but empty. No
alternate Personio tenant, locale, endpoint, or detail identifier may be guessed.

V28 proved canonical provider-detail URL shape alone is insufficient when unchanged
content proof fails.

V29 proved a different reusable principle: a **literal historical provider/listing
route may be replayed as a sensor entry only when that exact route was previously
observed, remains authorized, and is absent from the current retry surface**. Proof
still comes from a new metered detail GET or the existing runtime record proof, not
from the historical route itself.

The next inspection extends this principle beyond ATS-registry matches only if
historical evidence already contains literal job-related routes on current
authorized hosts.

## Deterministic hard boundaries

These remain unchanged:

- no company-specific success branch merely to increase cohort recall;
- no guessed ATS token, tenant, endpoint, selector, route, board, site, or job ID;
- no weakening of final genuine-job/content proof;
- provider detection alone is never authority;
- historical observation alone is never job proof;
- no model/provider hypothesis as Product truth;
- no raw HTML/API/XML body, credential, cookie, header, form value, request body,
  or secret persistence;
- no DB/Product/source activation/scheduler/application mutation in acquisition
  shadow work;
- ambiguous evidence fails closed;
- any promoted default rule requires focused positive/negative tests and fresh
  reusable evidence.

## Booster and ML boundaries

Pipeline `#522` remains the LLM/search booster authority for sparse, novel, or
semantic residuals after the strongest admissible deterministic surface. It has
not been invoked by V25–V29 and must not be pulled forward while evidence-backed
deterministic routes remain.

The ML learning foundation lane remains parallel and active. Productive decision
order remains deterministic authority first, then learned scoring/ML where
admitted, with the LLM/search booster as the expensive residual layer. Runtime
acquisition work does not replace or demote the ML lane.

## Sole next safe action

Inspect the exact **10-case V29 residual** against already-persisted sanitized V9,
V13, V26, V27, V28, and V29 evidence. For each case, identify only literal
job-related URLs/routes that satisfy all of the following:

1. the host is already current-authorized for that exact case;
2. the route was actually observed in prior evidence rather than inferred;
3. the route is public HTTPS and contains no persisted query value/secret;
4. the route is not an apply/login/privacy/static-asset surface;
5. the same normalized path has not already been exercised by V26/V28/V29;
6. replaying it grants no proof by itself — unchanged HTML/runtime proof remains
   mandatory.

If multiple cases expose the same reusable route family, select the strongest
cross-case generic family first. If only isolated routes exist, a bounded
read-only **observed-route replay diagnostic** may measure them without promoting a
company-specific production rule.

Any Runtime shadow must remain bounded and read-only, persist only sanitized URL
shapes and proof summaries, construct no new endpoint, and make no
provider/LLM/Tavily request beyond the already observed public page GETs emitted by
the browser.

If this 10-case inspection produces no admissible untried observed routes, record
that deterministic acquisition is exhausted for the bound cohort and hand the
remaining residual to booster admission. Do not broaden click semantics or guess
provider routes to avoid that conclusion.

## Re-entry status

Repository work is active. Current strict truth is **`30/40` proven, `10/40`
unresolved**. Static V4 route inference, generic visible interaction, the exact X1F
Personio feed, and canonical-provider-root detail privilege are exhausted at their
current evidence surfaces.

The sole next safe action is the exact 10-case historical observed-route inspection
described above. Deterministic acquisition is not declared exhausted until that
inspection is complete.
