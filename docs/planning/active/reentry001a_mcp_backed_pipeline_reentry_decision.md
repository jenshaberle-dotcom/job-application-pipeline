# REENTRY-001A Job Application Pipeline Re-Entry Decision

Status: current repository re-entry; deterministic runtime acquisition hardening active  
Date: 2026-08-25  
Repository: `jenshaberle-dotcom/job-application-pipeline`  
Repository ID: `1230805345`  
Current repository main at this slice start: `81eb232aad29a0e4c5f3d58cccc20eaee1073f26`  
Boundary: repository and Runtime evidence are project truth; chat is not project truth

## Purpose

This file is the canonical continuation point for the Job Application Pipeline.
The previous version is stale in one material respect: it treated the static
`23/40` V4 acquisition result as the stopping point for deterministic acquisition
and handed the full 17-case residual to booster admission.

That static conclusion remains correct only for the old bounded static observation
surface. Fresh Runtime evidence proved a reusable deterministic runtime/network
layer and advanced the strict measured cohort to **`28/40` proven and `12/40`
unresolved** without weakening acceptance, adding company-specific branches, or
using LLM/Tavily authority.

## Required reads

Before continuing from this point, authenticate repository ID `1230805345` and read:

1. this file completely;
2. Pipeline issue `#642` (`ACQ-RUNTIME-001`);
3. `docs/reference/search-intelligence/runtime_network_acquisition.md`;
4. merged Pipeline PRs `#645`, `#646`, and `#650`;
5. Runtime repository `jenshaberle-dotcom/job-pipeline-runtime`, issue `#203`;
6. Runtime issue #203 comment `5408661201`, the authoritative V24 checkpoint;
7. Runtime V24 run `32833964560` and carrier
   `carrier/203-static-route-proof-v24-32833964560`;
8. Pipeline issue `#522` (`LLM-BOOST-001`) and
   `docs/reference/search-intelligence/booster_admission.md`;
9. `docs/planning/active/ml_learning_foundation_lane.md`.

Do not substitute assistant memory, chat summaries, retired NEXT artifacts, stale
planning notes, or superseded PR descriptions for these sources.

## Repository delta since the prior re-entry

The prior re-entry froze the static V4 result at `23/40` and correctly rejected
further speculative static-route guessing. After that checkpoint, fresh evidence
changed the available deterministic observation surface:

- PR `#645` added provider/company-agnostic structured runtime payload recognition;
- PR `#646` added fail-closed runtime job-record proof and bounded one-hop candidate
  host delegation;
- Runtime browser/network evidence produced genuine incremental strict rescues;
- PR `#650` added an explicit fail-closed public-inventory delegation contract for
  already-authorized pages and observed inventory hosts;
- Runtime V24 completed authoritatively after its harness/transport boundedness was
  repaired and added one additional strict rescue;
- the current repository main later advanced to `81eb232a...` through RCC/project
  hygiene changes that do not modify acquisition semantics.

Open PR `#647` was written against the much earlier `42157f...` / `24/40` state and
is superseded by this re-entry refresh. It must not be treated as current project
truth.

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

Runtime issue #203 comment `5408661201` is the current cohort checkpoint.
Authoritative V24 run `32833964560` executed against Pipeline
`e0d55f8d2470fca5f0673943d83f2a3df3342d14` and exact Runtime base
`bcf5414f29b6651c55a0f96c6deeceb9a6a58429`.

The result is:

- V4 static baseline: `23/40`;
- subsequent strict deterministic rescues before V24: `+4`;
- V24 strict rescue: `+1`;
- **current strict proven: `28/40`**;
- **current unresolved: `12/40`**;
- diagnostic execution failures: `0`;
- response-drain timeouts: `0`;
- context-close failures: `0`.

The earlier V24 runs `32782000620`, `32832864569`, and `32833522237` were technical
harness/transport failures. They are not 0-rescue evidence and must not be counted
against the acquisition strategy.

## Current deterministic authority

The active deterministic runtime contract is ACQ-RUNTIME-001:

```text
authorized public career/listing page
-> bounded browser observation
-> optional bounded visible listing interaction
-> transient structured response
-> generic runtime payload recognition
-> runtime job-record proof
-> bounded observed inventory/delegated-host authority where proven
-> unchanged downstream acquisition authority
```

The browser remains an evidence sensor. Neither page rendering nor a click grants
host, source, job, lifecycle, ranking, application, or Product authority.

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

Fresh V24 evidence selects the next generic deterministic hardening slice: bounded
multi-step visible listing interaction before another runtime observation pass.

The pure Pipeline policy is `src/search_intelligence/runtime_listing_interaction.py`.
It authorizes only one next interaction decision at a time and requires the Runtime
adapter to rescan the live visible controls after every action.

Default per-page budget:

```text
max_total_actions = 3
max_click_actions = 2
max_scroll_actions = 1
```

Eligible generic families:

- explicit load/show/view-more jobs or positions;
- explicit next-page/jobs controls, with plain `next` requiring job context;
- explicit jobs/open-jobs/search-jobs/view-jobs controls;
- one bounded scroll probe when no fresh eligible click is available.

Fail-closed exclusions include unauthorized pages, hidden/disabled controls,
apply/submit/login/register/upload/contact controls, filter/sort/privacy/cookie
noise, non-link/non-button controls, non-HTTPS explicit absolute hrefs, repeated
control fingerprints, inconsistent progress, and exhausted budgets.

The policy persists no selector or DOM snapshot. Secret-like query values are
redacted before control fingerprinting.

## Deterministic hard boundaries

These boundaries remain unchanged:

- no company-specific success branch merely to increase cohort recall;
- no guessed ATS token, tenant, endpoint, selector, or route;
- no weakening of final genuine-job/content proof;
- provider detection alone is never authority;
- no model/provider hypothesis as Product truth;
- no raw HTML/API body, credential, cookie, header, form value, or secret
  persistence;
- no DB/Product/source activation/scheduler/application mutation in acquisition
  shadow work;
- ambiguous evidence fails closed;
- any promoted default rule requires focused positive/negative tests and fresh
  cross-company Runtime evidence.

## Booster and ML boundaries

Pipeline `#522` remains the LLM/search booster authority for sparse, novel, or
semantic residuals after the strongest admissible deterministic surface. It does
not supersede ACQ-RUNTIME-001 and is not invoked by Slice 3A.

The ML learning foundation lane remains parallel and active. Its first planned
value surface remains `job_review_relevance`; runtime acquisition work neither
replaces nor demotes that lane.

## Sole next safe action

Complete and merge ACQ-RUNTIME-001 Slice 3A only after focused tests and exact-head
Pipeline validation are green. Then Runtime must consume the exact merged Pipeline
SHA and run the current **12-case** residual through a bounded read-only interaction
shadow using the existing runtime structured-response proof/delegation authority.

That Runtime proof must report interaction families/counts, truncation/failure
states, runtime-record proofs, strict incremental rescues, and the resulting exact
40-cohort total. It must perform no LLM/Tavily/provider call and no
DB/Product/source/application write.

Only that fresh evidence may select the next deterministic mutation. Do not invent
a provider/company-specific adapter or broaden interaction semantics merely to
raise the score.

## Re-entry status

Repository work is active. Static V4 route inference remains exhausted at its old
surface, but deterministic runtime acquisition is not exhausted. Current strict
truth is **`28/40` proven, `12/40` unresolved**, and the evidence-backed next slice
is bounded visible listing interaction followed by a fresh Runtime shadow.
