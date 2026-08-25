# REENTRY-001A Job Application Pipeline Re-Entry Decision

Status: current repository re-entry; deterministic runtime acquisition hardening active  
Date: 2026-08-25  
Repository: `jenshaberle-dotcom/job-application-pipeline`  
Repository ID: `1230805345`  
Current repository main at this slice start: `657d4c84a03a0327d152eb5c158a005166b4bfbb`  
Boundary: repository and Runtime evidence are project truth; chat is not project truth

## Purpose

This file is the canonical continuation point for the Job Application Pipeline.
The immediately previous version is stale in one material respect: it stopped at
the authoritative V24 checkpoint of `28/40` strict proven and `12/40` unresolved,
and still described ACQ-RUNTIME-001 Slice 3A visible listing interaction as the next
safe action.

Slice 3A has since been merged and exercised by fresh Runtime evidence. V25 rescued
one additional candidate without changing proof authority, while V26 and V27
hardened and extended deterministic acquisition but produced no further strict
rescues. The current measured cohort is therefore **`29/40` proven and `11/40`
unresolved**.

The generic visible-interaction surface is now evidence-exhausted for this bound
cohort. Deterministic acquisition as a whole is not yet declared exhausted until
the exact 11-case residual has been inspected for other already-observed,
provider-family/public-inventory protocols.

## Required reads

Before continuing from this point, authenticate repository ID `1230805345` and read:

1. this file completely;
2. Pipeline issue `#642` (`ACQ-RUNTIME-001`);
3. `docs/reference/search-intelligence/runtime_network_acquisition.md`;
4. merged Pipeline PRs `#645`, `#646`, `#650`, and `#653`;
5. Runtime repository `jenshaberle-dotcom/job-pipeline-runtime`, issue `#203`;
6. Runtime issue #203 comment `5412094990`, the authoritative V27 checkpoint;
7. Runtime V25 run `32842742734`, V26 run `32859303936`, and authoritative V27
   retry run `32860970408`;
8. V27 persisted evidence at branch
   `carrier/203-personio-public-feed-v27-32860970408`, path
   `carriers/connector-personio-public-feed-v27/32860970408/result.json`;
9. Pipeline issue `#522` (`LLM-BOOST-001`) and
   `docs/reference/search-intelligence/booster_admission.md`;
10. `docs/planning/active/ml_learning_foundation_lane.md`.

Do not substitute assistant memory, chat summaries, retired NEXT artifacts, stale
planning notes, or superseded PR descriptions for these sources.

## Repository delta since the prior re-entry

The prior re-entry correctly established V24 as `28/40` and selected bounded
visible listing interaction as the next generic deterministic slice. Since then:

- Pipeline PR `#653` merged the pure fail-closed Slice 3A policy for bounded visible
  listing interaction;
- Runtime V25 executed that policy over the bound residual and rescued candidate
  `37` / E.ON Grid Solutions through a real visible-detail transition followed by
  the unchanged genuine-job proof (`jsonld_jobposting`);
- V25 therefore advanced the strict cohort from `28/40` to `29/40`;
- Runtime V26 hardened the same interaction harness by rejecting static-asset seeds
  and decoupling click dispatch from navigation waiting;
- V26 produced `0` additional strict rescues, `0` runtime proofs, and no case-level
  drain/context failures, leaving `29/40` and `11/40` unresolved;
- Runtime V27 reused the existing Pipeline Personio provider/target-authority
  contract rather than inventing a new route;
- only candidate `33` / X1F was eligible for that exact Personio path;
- `https://x1f.jobs.personio.de/xml?language=de` returned HTTP `200` but contained
  `0` positions, so feed/employer authority deliberately failed closed and no
  detail request was attempted;
- V27 therefore produced `0` additional rescues and left the strict cohort at
  `29/40`;
- V27 run `32860548943` was a technical harness failure caused by an accidental
  V18/Playwright helper dependency before any Personio GET. It is not acquisition
  evidence. PR `#307` removed that dependency and retry run `32860970408` is the
  authoritative V27 evidence;
- Runtime execution-only retry carrier PR `#308` was closed unmerged after the
  authoritative evidence had been persisted.

Open PR `#647` was written against the much earlier `42157f...` / `24/40` state and
remains superseded. It must not be treated as current project truth.

## Static V4 control baseline

The fixed static control remains the post-PR-#639 V4 proof:

- input: `40`;
- strict genuine-job acquisition proven: `23`;
- blocked: `17`;
- blocked reason: `no_genuine_job_detail` for all 17;
- static request contract unchanged: base 3 plus only the existing shared fourth
  request, absolute static cap 4;
- provider/LLM/Tavily requests: `0`;
- Product/DB/source/application mutation: `0`.

This result is not rewritten by later runtime campaigns. Runtime lift is measured
incrementally against it.

## Current authoritative acquisition truth

Runtime issue #203 comment `5412094990` is the current cohort checkpoint.
Authoritative V27 retry run `32860970408` executed against Pipeline
`657d4c84a03a0327d152eb5c158a005166b4bfbb`, exact Runtime base
`6605a9de0f88a48634745a6c89fc4bce40288717`, and authoritative V26 run
`32859303936`.

The result chain is:

- V4 static baseline: `23/40`;
- deterministic strict rescues through V24: `+5`;
- V25 visible interaction: `+1` — candidate `37` / E.ON Grid Solutions;
- V26 interaction harness hardening: `+0`;
- V27 Personio public-feed proof: `+0`;
- **current strict proven: `29/40`**;
- **current unresolved: `11/40`**.

V26 additionally reported:

- diagnostic execution failures: `0`;
- response-drain timeouts: `0`;
- context-close failures: `0`;
- runtime proof count: `0`;
- strict hardening rescues: `0`.

V27 additionally proved:

- Personio-eligible residual cases: `1`;
- exact eligible case: candidate `33` / `x1f`;
- exact public Personio feed route: HTTP `200`;
- feed positions returned: `0`;
- validated feed authority count: `0`;
- detail attempts: `0`;
- strict Personio rescues: `0`;
- fail-closed reason: `personio_xml_has_no_positions`.

The failed V27 run `32860548943` is not a zero-rescue result; it failed before the
provider-family request because of a technical import dependency and produced no
acquisition evidence.

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
-> existing provider-family public-inventory authority where exact identity is proven
-> unchanged downstream acquisition authority
```

The browser remains an evidence sensor. Neither page rendering nor a click grants
host, source, job, lifecycle, ranking, application, or Product authority.
Provider-family recognition likewise does not grant tenant/employer authority by
itself.

### Runtime structured-response proof

`src/search_intelligence/runtime_network_acquisition.py` is already merged and owns:

- bounded JSON traversal;
- secret-like query redaction;
- generic job-context recognition;
- explicit non-job-container precedence;
- `runtime_job_record_proof`;
- `runtime_page_delegated_inventory_record`;
- bounded one-hop delegated candidate-host authority after proof.

No raw runtime response is persistent truth.

### Slice 3A — visible listing interaction

Slice 3A is now implemented and evidence-tested. The pure Pipeline policy remains
`src/search_intelligence/runtime_listing_interaction.py` with the default per-page
budget:

```text
max_total_actions = 3
max_click_actions = 2
max_scroll_actions = 1
```

Eligible generic families remain:

- explicit load/show/view-more jobs or positions;
- explicit next-page/jobs controls, with plain `next` requiring job context;
- explicit jobs/open-jobs/search-jobs/view-jobs controls;
- one bounded scroll probe when no fresh eligible click is available.

Fail-closed exclusions remain unchanged, including unauthorized pages,
hidden/disabled controls, apply/submit/login/register/upload/contact controls,
filter/sort/privacy/cookie noise, non-link/non-button controls, non-HTTPS explicit
absolute hrefs, repeated control fingerprints, inconsistent progress, and exhausted
budgets.

V25 proved that this slice can add strict recall (`+1`). V26 then removed two
generic harness artefacts but yielded no further proof across the remaining cases.
For the bound 40-case cohort, **generic click/scroll broadening is now exhausted and
must not be extended merely to chase recall**.

### Provider-family public inventory

The repository already contains deterministic ATS/provider recognition and
provider-specific authority contracts. V27 exercised the existing Personio path
only where an already-observed authorized Personio hostname exposed a concrete
target hint and the employer had reviewed identity evidence.

That path is now also exhausted for the current X1F evidence: the exact public XML
feed is real but currently empty. No Personio endpoint, tenant, locale variant, or
detail identifier may be guessed to manufacture inventory.

This does not yet prove that all deterministic provider-family opportunities are
exhausted across the other 10 non-Personio residual cases.

## Deterministic hard boundaries

These boundaries remain unchanged:

- no company-specific success branch merely to increase cohort recall;
- no guessed ATS token, tenant, endpoint, selector, route, board, site, or job ID;
- no weakening of final genuine-job/content proof;
- provider detection alone is never authority;
- no model/provider hypothesis as Product truth;
- no raw HTML/API/XML body, credential, cookie, header, form value, or secret
  persistence;
- no DB/Product/source activation/scheduler/application mutation in acquisition
  shadow work;
- ambiguous evidence fails closed;
- any promoted default rule requires focused positive/negative tests and fresh
  cross-company or provider-family evidence.

## Booster and ML boundaries

Pipeline `#522` remains the LLM/search booster authority for sparse, novel, or
semantic residuals after the strongest admissible deterministic surface. It does
not supersede ACQ-RUNTIME-001 and has not been invoked by V25–V27.

The ML learning foundation lane remains parallel and active. Its first planned
value surface remains `job_review_relevance`; runtime acquisition work neither
replaces nor demotes that lane.

## Sole next safe action

Inspect the exact **11-case V27 residual** using only already-persisted sanitized
V26/V27 and earlier provider-family evidence. Determine whether any unresolved
cases expose another **already-observed** ATS/public-inventory protocol with enough
exact board/tenant/site/host identity to support a bounded, read-only,
provider-generic deterministic adapter.

The inspection itself must make no new provider/LLM/Tavily request and no
DB/Product/source/application write.

If such a protocol exists, select at most the strongest reusable provider-family
slice, add focused positive/negative tests, and run a separately authorized bounded
Runtime shadow with unchanged host and genuine-job proof authority.

If the 11-case inspection yields no such evidence-backed reusable protocol, record
that deterministic acquisition is exhausted for this bound cohort and hand the
remaining residual to the existing booster-admission path. Do **not** broaden
visible click/scroll semantics further and do **not** try alternate Personio
endpoints or guessed provider routes.

## Re-entry status

Repository work is active. Static V4 route inference is exhausted at its bounded
surface. Generic visible interaction is also exhausted for this bound cohort, and
the exact existing Personio public-feed path produced no current inventory.

Current strict truth is **`29/40` proven, `11/40` unresolved**. The only remaining
deterministic question is whether the exact 11-case residual already contains
sufficient observed authority for another reusable provider-family/public-inventory
protocol. That inspection is the sole next safe action.
