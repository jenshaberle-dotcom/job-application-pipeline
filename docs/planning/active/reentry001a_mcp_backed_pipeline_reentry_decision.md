# REENTRY-001A Job Application Pipeline Re-Entry Decision

Status: current repository re-entry; static acquisition hardening exhausted, runtime/API promotion active
Date: 2026-08-24
Repository: `jenshaberle-dotcom/job-application-pipeline`
Repository ID: `1230805345`
Current Pipeline main: `42157f11774dd60ae86b0b02ba1fe71a42e03d4c`
Boundary: repository and Runtime evidence are project truth; chat is not project truth

## Purpose

REENTRY-001A is the repository-backed continuation point for the Job Application
Pipeline. The former June GENERIC/EXPAND next action and the later statement that
all deterministic acquisition work stopped at the static `23/40` V4 result are
stale.

The correct distinction is now:

- the **static bounded V4 acquisition surface** is exhausted at `23/40` for the
  bound cohort under its four-request contract;
- hardened runtime observation has already produced one additional strict rescue,
  taking the measured authority-preserving baseline to `24/40`;
- `ACQ-RUNTIME-001` Slice 2 is merged and provides generic runtime job-record proof
  plus bounded one-hop delegation without provider/company exceptions;
- documented public ATS APIs/feeds and repeatedly observed runtime protocols are
  now an authorized deterministic optimization path, but only after employer and
  tenant/board authority is established;
- LLM/search remains the fallback for residuals that still lack an authorized
  structured route after those cheaper deterministic/runtime surfaces are tested;
- the parallel ML learning lane remains preserved and is not superseded by this
  acquisition work.

## Required reads

Before continuing, authenticate the repository ID above and read:

1. this file completely;
2. `docs/reference/search-intelligence/ats_api_acquisition_strategy.md`;
3. Pipeline issue `#642` (`ACQ-RUNTIME-001`) and the merged Slice-2 implementation
   at Pipeline commit `42157f11774dd60ae86b0b02ba1fe71a42e03d4c`;
4. Pipeline issue `#522` (`LLM-BOOST-001`) and
   `docs/reference/search-intelligence/booster_admission.md`;
5. `docs/planning/active/ml_learning_foundation_lane.md`;
6. Runtime repository `jenshaberle-dotcom/job-pipeline-runtime`, issue `#203`;
7. Runtime V4 run `32670547466`, result commit
   `32f8cf904de6165c7aa60c2b74de00d41f263473`;
8. Runtime V16 run `32671012052`, result commit
   `c4b540658de4f083230361ef96dd8da7928e283a`;
9. Runtime V17 candidate-validation run `32697818259`, carrier
   `carrier/203-network-v17-candidate-validation-32697818259`;
10. the latest V18 runtime-authority shadow evidence described below.

Do not substitute assistant memory, chat summaries, retired NEXT artifacts, or
stale generated summaries for these sources.

## Historical static deterministic delta

The static V4 hardening campaign improved the bound 40-candidate cohort from
`21/40` to `23/40` without increasing the absolute four-request cap or weakening
proof. Relevant merged generic slices include:

- `#615`: Deloitte deterministic acquisition repair;
- `#616`: bounded sibling fallback after a discovered detail attempt fails;
- `#623`: strict same-host `stellenmarkt` / `stellenanzeige` requisition-detail
  use of the existing shared fourth request;
- `#639`: reuse of the same strong requisition boundary in the form-aware lane.

The authoritative static proof remains Runtime V4 run `32670547466`:

- input `40`;
- genuine-job acquisition proven `23`;
- blocked `17`;
- every block cause `no_genuine_job_detail`;
- logical network requests `110`;
- proof-job persistence `0`.

That V4 result remains the fixed static control baseline. Later runtime evidence is
measured as incremental lift against it rather than silently rewriting the V4
artifact.

## V16 residual evidence

Runtime V16 run `32671012052` is bound to the same 17 V4 residual cases and
completed its diagnostic lanes with zero execution failures. It did not justify a
new static route under the old contract: provider detection, API/form hints and
static assets did not establish a new authorized genuine-job transition.

That earlier exhaustion decision remains valid specifically for **static route
inference**. It does not prohibit using genuinely new evidence from a browser
runtime transaction or a documented public provider interface.

## V17 runtime evidence and measured baseline

The hardened V17 browser/network campaign supplied new evidence that did not exist
in V16. Runtime candidate validation run `32697818259` kept acceptance unchanged,
made no DB/Product/source mutation, made no LLM/Tavily requests, and did not use a
known-detail privilege.

Its strict measured result is:

- static V4 proven baseline: `23/40`;
- additional strict current-authority rescue: `1`;
- effective strict baseline: **`24/40`**;
- unresolved after that strict rescue: `16`.

Important exemplars:

- **AOK Niedersachsen**: same-host runtime evidence produced a genuine detail and
  is the one strict V17 rescue;
- **TrustYou / JOIN**: runtime evidence produced genuine JOIN detail URLs, but the
  V17 authority model did not yet permit the observed one-hop provider inventory
  delegation;
- **Clarios / Workday**: runtime evidence exposed structured Workday inventory and
  real Workday detail targets, but the provider host was not yet authorized by the
  pre-Slice-2 static authority model.

Do not count TrustYou or Clarios as rescued from V17 alone.

## ACQ-RUNTIME-001 Slice 2

Pipeline commit `42157f11774dd60ae86b0b02ba1fe71a42e03d4c` is the current runtime
acquisition authority. It adds:

- bounded recognition of structured runtime job records;
- runtime job-record proof that remains separate from mere candidate recognition;
- bounded one-hop candidate-host delegation from an authorized runtime response;
- negative-container precedence so generic objects under explicit non-job
  containers such as products/news/articles/content cannot become job proof merely
  because the endpoint path looks job-related;
- focused positive and negative regression coverage.

Full repository CI passed before merge. Slice 2 does not change the static V4
acceptance rule and grants no provider/company-specific exception.

## V18 runtime-authority shadow

V18 replays the same 17 V4 residuals and applies Slice-2 runtime recognition/proof
directly to transient structured responses. It is shadow/read-only:

- no DB/Product/source/application mutation;
- no provider LLM or Tavily calls;
- no raw HTML, raw response bodies, request bodies, headers, cookies, tokens or
  query values persisted;
- bounded seeds, structured-response count and navigation timeout;
- exact V4/V16/V17 identity binding before browser execution.

Runtime transport hardening completed on 2026-08-24:

- the trigger uses the repository-working `pull_request` event;
- executable Runtime code is pinned to trusted snapshot
  `a08e3f91cece4e8e2986bdf862e5003dbf41c754`;
- the browser runs in the same official Playwright
  `mcr.microsoft.com/playwright/python:v1.55.0-noble` container already proven by
  V17, instead of relying on host Chromium libraries.

Current live V18 run while this re-entry update is being written:
`32724834560`.

Until its carrier is persisted and reviewed, the authoritative measured baseline
remains **24/40**, not a projected higher value.

## API/feed acquisition strategy

API/feed acquisition is now a first-class deterministic optimization path, defined
in `docs/reference/search-intelligence/ats_api_acquisition_strategy.md`.

Repository precedent already includes Greenhouse board API, selected Personio XML
feeds and the Bundesagentur public API. The ATS provider registry also recognizes
Workday, SmartRecruiters, Lever, Ashby, Recruitee, JOIN and other families, but
provider recognition alone explicitly grants no tenant, delegation or Product
authority.

Current provider documentation additionally makes several structured surfaces
credible provider-family adapter targets, including Lever Postings API, Ashby Job
Postings API and SmartRecruiters Posting API. They may only be used when the
required board/site/company identifier has been observed from an
employer-authorized surface. Workday is treated differently: current project
evidence supports learning its runtime protocol, not guessing a generic tenant
route.

Acquisition-specific preference order:

`documented public API/feed -> observed stable provider protocol -> bounded browser runtime -> search/LLM booster`

This order minimizes browser/provider cost while preserving the same truth
boundary. It is not a global replacement for task-specific ML/LLM admission.

## API/provider admission gate

A new provider-family adapter is authorized only if all applicable gates hold:

1. employer origin authority is already proven;
2. provider family is observed, not guessed;
3. tenant/board/site/company identifier is observed from an authorized surface;
4. route is provider-documented public job infrastructure or has repeated runtime
   protocol evidence sufficient for a separately tested generic adapter;
5. requests/results/time are bounded;
6. returned records pass runtime job-record proof or yield detail URLs that pass
   existing genuine-job proof;
7. provider detection alone never grants a guessed route or host.

No credentialed customer API, application-submission API, provider exception,
guessed tenant, raw response persistence, or Product/source mutation is authorized
by this decision.

## Deterministic contract

The following boundaries remain hard:

- static V4 base request budget remains `3`, with at most the existing shared
  fourth request and absolute static cap `4`;
- runtime/API requests use their own explicit bounded campaign/adapter budgets and
  do not silently enlarge V4;
- genuine-job proof remains fail-closed;
- provider recognition is evidence, not authority;
- no company-specific exception merely to raise the 40-cohort score;
- no DB, Product, source activation, scheduler or application mutation in shadow
  acquisition work;
- ambiguous evidence fails closed.

A successful runtime/API adapter may later be promoted into default deterministic
acquisition only after focused positive/negative/cross-tenant tests and a fresh
40-cohort proof.

## Sole next action

1. Complete and review V18 run `32724834560` and persist its sanitized carrier.
2. Recompute the strict baseline using only V18 proofs admitted by Slice 2.
3. Group the still-unresolved residual by ATS/provider family and by whether a
   deterministic tenant/board identifier exists.
4. Implement the **highest-reuse authorized structured adapter** first:
   documented public API/feed when available, otherwise a repeatedly evidenced
   runtime protocol such as Workday CXS only after its tenant/route contract is
   generically proven.
5. Run a fresh bounded residual shadow before changing default acquisition.
6. If a provider adapter is promoted into deterministic default acquisition, run
   a new V4 40-cohort proof followed by a fresh residual evidence gate.
7. Send only the remaining sparse/novel cases to the `#522` LLM/search cascade.

Do not reopen speculative static-route scraping. New deterministic work must be
backed by runtime/API evidence and remain generic.

## Parallel ML lane

The ML learning lane remains active and preserved. Nothing in ACQ-RUNTIME-001,
V18, or the ATS API strategy deletes, demotes or rewrites the existing ML work.
Acquisition and ML may progress independently under their respective authority
contracts.

## Re-entry status

Repository work is active. The current phase is **runtime/API deterministic
promotion after static exhaustion**, with strict measured authority at `24/40`
until V18 proves additional rescues. The sole continuation point is the V18 result
followed by evidence-driven provider-family adapter selection.