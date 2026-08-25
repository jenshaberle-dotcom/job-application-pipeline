# ACQ-RUNTIME-001 Runtime / Network Acquisition

Status: active deterministic implementation contract  
Date: 2026-08-25  
Authority: Pipeline issue #642  
Current repository main before Slice 3A: `81eb232aad29a0e4c5f3d58cccc20eaee1073f26`

## Why this layer exists

The static V4 acquisition surface reached an evidence-supported ceiling at `23/40`
genuine-job proofs and `17/40` `no_genuine_job_detail` residuals under its existing
four-request contract. That result remains the fixed static control baseline.

Runtime evidence later proved that the deterministic layer itself was not exhausted:
the missing information was frequently absent from the static response and appeared
only after client execution through XHR/fetch/GraphQL/POST, runtime-rendered routes,
public inventory widgets, or other structured browser traffic.

The browser is therefore an observation mechanism, not an authority mechanism.
Runtime evidence may unlock additional deterministic transitions only through
explicit bounded contracts.

## Current measured truth

The authoritative Runtime issue #203 evidence now records:

- static V4 baseline: `23/40`;
- subsequent strict deterministic rescues before V24: `+4`;
- authoritative V24 rescue: `+1`;
- current strict proven: **`28/40`**;
- current unresolved: **`12/40`**.

Authoritative V24 run: `32833964560` against Pipeline
`e0d55f8d2470fca5f0673943d83f2a3df3342d14`. The later Pipeline main changes to
`81eb232aad29a0e4c5f3d58cccc20eaee1073f26` are RCC/project-hygiene changes and do
not alter acquisition semantics.

The earlier V24 runs `32782000620`, `32832864569`, and `32833522237` were technical
harness/transport failures and are not negative acquisition evidence.

## Target flow

```text
career/listing page
    -> bounded browser execution
    -> optional bounded visible listing interaction
    -> network observation
    -> structured response recognition
    -> deterministic runtime job-record proof
    -> bounded one-hop delegated inventory authority when proven
    -> candidate detail/runtime evidence
    -> existing final acquisition authority
```

No interaction, provider marker, candidate object, or browser event is Product truth
by itself.

## Runtime structured-response authority

`src/search_intelligence/runtime_network_acquisition.py` owns the pure runtime
network contract. It:

- sanitizes persistable request/response/page URLs;
- redacts secret-like query values;
- traverses transient JSON with explicit node/depth/candidate bounds;
- recognizes provider/company-agnostic job-shaped records;
- gives explicit non-job containers precedence over endpoint job context;
- separates recognition from `runtime_job_record_proof`;
- permits the bounded `runtime_page_delegated_inventory_record` proof only when an
  already-authorized browser page observes a strong structured job record whose
  candidate URL remains on the observed cross-host inventory response;
- permits one-hop candidate-host delegation only after runtime job-record proof;
- persists no raw response body, cookies, headers, form values, credentials, or
  browser state.

This authority was implemented by Pipeline PRs #645 and #646 and then extended by
PR #650 with the explicit public-inventory delegation contract. Provider/company
exceptions are not encoded.

## Slice 3A — bounded visible listing interaction policy

Fresh authoritative V24 evidence selects the next generic deterministic surface:
a bounded sequence of visible listing interactions before another structured
runtime observation pass.

`src/search_intelligence/runtime_listing_interaction.py` owns the pure selection
policy. The Runtime browser adapter remains outside the module.

### Allowed evidence

The caller may provide only sanitized metadata for controls that are currently
visible in an already-authorized public career/listing page:

- role;
- visible text;
- ARIA label;
- explicit href when present;
- small local context text;
- visible/enabled state.

No DOM selector, script body, hidden element, form value, cookie, credential, token,
or raw page snapshot becomes durable authority.

### Generic interaction families

The first bounded families are:

1. `load_more` — explicit load/show/view-more jobs or positions controls;
2. `next_page` — explicit next-page/jobs controls, with generic `next` accepted only
   on job-context pages;
3. `open_jobs` — explicit jobs/open-jobs/search-jobs/view-jobs controls;
4. one bounded `scroll` probe only when no fresh eligible click is available.

The default per-page budget is:

```text
max_total_actions = 3
max_click_actions = 2
max_scroll_actions = 1
```

The Runtime caller must rescan the currently visible controls after every selected
action and invoke the pure selector again with updated progress. This avoids
planning future clicks against stale DOM state.

### Fail-closed behavior

The policy rejects:

- unauthorized pages;
- hidden or disabled controls;
- non-link/non-button controls;
- explicit non-HTTPS absolute hrefs;
- apply/submit/login/register/upload/contact controls;
- filter/sort/privacy/cookie/noise controls;
- generic `load more` or plain `next` outside job context;
- repeated control fingerprints;
- inconsistent progress state;
- any action after the configured budget is exhausted.

Control fingerprints use only normalized sanitized metadata; secret-like query
values are redacted before hashing.

A selected click or scroll grants **zero** host, source, candidate, job, lifecycle,
ranking, application, or Product authority. Any newly observed structured response
must still pass the existing ACQ-RUNTIME-001 runtime recognition/proof contracts.

## Next Runtime proof after Slice 3A merge

Runtime should consume the exact merged Pipeline SHA and execute the current
remaining 12-case residual in shadow/read-only mode with:

- the default bounded interaction budget above;
- fresh visible-control rescans after each action;
- transient structured-response parsing only;
- the existing `runtime_page_delegated_inventory_record` and related runtime proof
  authority unchanged;
- no guessed ATS token, tenant, endpoint, selector, or company-specific rule;
- no raw body/HTML persistence;
- no provider/LLM/Tavily calls;
- no DB/Product/source/application mutation.

The result must report interaction counts/reason codes, runtime-record proof counts,
strict incremental rescues, diagnostic failures/truncations, and a new exact
40-cohort acquisition total. A default-path promotion requires cross-company
evidence plus focused positive/negative Pipeline tests.

## Relationship to LLM/search and ML

LLM/search remains a separate task-specific booster path under #522 and
`BOOSTER-ADMISSION-001`; it does not replace runtime determinism and is not invoked
by Slice 3A. The ML learning foundation lane remains parallel and untouched.

## Hard boundaries

- no company-specific success branch;
- no weakening of final genuine-job/content proof;
- no provider/model result as authority;
- no guessed ATS token, endpoint, tenant, or route;
- no credential/token/cookie/form-value persistence;
- no raw runtime response or HTML persistence by default;
- no DB/Product/source activation/application mutation in shadow discovery;
- bounded execution with explicit fail-closed state;
- any production/default-path promotion requires fresh cross-company evidence and
  repository validation.
