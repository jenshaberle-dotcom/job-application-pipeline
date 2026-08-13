# LLM-BOOST-001 — Search-first semantic booster cascade

Status: implementation contract
Authority: Issue #522

## Purpose

LLM-BOOST-001 adds bounded semantic generalization to Search Intelligence where
additional deterministic special cases stop scaling. It does not replace the
deterministic pipeline and it does not grant provider/model output product
authority.

The canonical escalation order is:

```text
deterministic
-> Tavily when applicable and operational/budgeted
-> GPT-5.6 Luna (medium)
-> GPT-5.6 Terra (medium)
-> GPT-5.6 Sol (medium)
-> GPT-5.6 Luna (max)
-> bounded deep evidence / adjudication
-> deterministic validator / lifecycle authority
```

`Pro` mode is not part of the normal cascade. Accepted origin residual evidence
showed zero additional rescues in the measured Pro+max residual campaign at
materially higher cost and latency.

## Core authority rule

Provider/model stages may:

- propose URLs, board roots or detail candidates;
- classify ambiguous page/route structure;
- extract structured semantic fields with evidence spans;
- classify a repair family;
- propose a next bounded diagnostic.

Provider/model stages may not directly establish:

- employer identity;
- employer-to-ATS authority;
- concrete-detail truth;
- a gate pass;
- connector/source activation;
- Bronze/Silver/Gold lifecycle truth;
- ranking/product suitability authority;
- application generation/submission authority.

Those decisions remain bound to existing deterministic validators and governed
writers.

## Why Tavily precedes the model cascade

Tavily is an information-acquisition stage. Luna/Terra/Sol/max are semantic
reasoning stages. When the unresolved state is caused by missing public-web
information, acquiring evidence before spending more reasoning budget is the
preferred order.

Tavily is therefore the first provider escalation where external search is
applicable. This ordering does **not** make Tavily a prerequisite for the later
model stages.

### Required Tavily states

| State | Tavily action | Later model cascade |
|---|---|---|
| `available` | eligible within request/credit budget | continue only if unresolved |
| `disabled` | skip | continue |
| `missing_key` | skip | continue |
| `budget_exhausted` | skip | continue |
| `insufficient_budget_for_next_request` | skip | continue |
| `provider_unavailable` | fail/skip closed | continue when no safety invariant is violated |
| `unknown` | skip closed | continue |

Tavily budget/key/provider state must never turn an unresolved deterministic
result into success and must never prevent Luna from running merely because
search is unavailable.

## Surfaces along the current hardening path

### `origin_discovery`

Deterministic company/career-origin hypotheses remain first. Tavily is normally
applicable after a deterministic miss. Model URLs remain untrusted until the
existing company-identity and career-origin validator accepts them.

### `listing_discovery`

Deterministic DOM/link/JSON-LD/iframe/redirect evidence remains first. Tavily is
not a routine listing fetch replacement and is eligible only for a diagnosed
external-information gap. Models may classify likely listing structure but do
not establish employer authority.

### `ats_delegation`

Deterministic employer-page-backed config/script/link evidence remains first.
Models may separate telemetry/noise from plausible ATS board/root evidence and
propose structured delegation hypotheses. A hostname or provider brand alone
never proves employer-to-ATS authority.

### `detail_discovery`

Deterministic concrete URL/ID/route evidence remains first. Models may propose
or classify unusual concrete-detail structures only after the bounded
deterministic path is unresolved. Same-employer/source validation remains
mandatory.

### `detail_semantics`

Known schema fields, structured metadata and deterministic term logic remain
first. Models may extract role, seniority, skills, location and remote semantics
with bounded evidence references. Existing product profile/geography contracts
decide whether the extracted evidence is sufficient.

### `recurring_connector`

Recurring execution has a stricter economic boundary than one-time discovery.
An unchanged supported evidence fingerprint must cause zero provider/model
calls.

The semantic cache identity is:

```text
connector_id
+ source-local job identity/URL
+ normalized evidence hash
+ booster contract version
```

Changed evidence may become booster-eligible. Tavily is still only applicable
when a classified external-information/search-recall gap exists; ordinary
semantic ambiguity should proceed directly from deterministic parsing into the
model cascade.

## Cost model

The accepted 2026-08-12 GPT-5.6 origin campaigns and the matching operator usage
export provide the initial planning means for the compact origin-hypothesis
prompt family:

| Stage | Observed planning mean / call | Current hard ceiling |
|---|---:|---:|
| Luna medium | about `$0.00494` | `$0.01` |
| Terra medium | about `$0.01124` | `$0.02` |
| Sol medium | about `$0.02650` | `$0.05` |
| Luna max | about `$0.01538` on the small residual sample | `$0.05` |

These are observations, not universal prices for every semantic task.
Listing/ATS/detail/recurring prompts may carry larger evidence payloads and must
run their own token/cost smoke campaigns before default promotion.

The accepted 17-case origin model sweep produced ordered validated lift:

```text
Luna: 10 rescues
Terra after Luna misses: +2
Sol after Luna+Terra misses: +1
medium residual: 4
Luna max residual campaign: +1
```

Using those observed stage-reach rates, the planning expectation for model cost
*after an origin deterministic miss* is about `$0.02098`, excluding Tavily.
The sum of all four model planning means (`$0.05806`) is a nominal all-stages
path, not the expected cascade bill because most cases stop earlier.

## Two economic regimes

### One-time / rare source discovery

Employer origin, listing and ATS discovery create reusable source capability.
Optimize primarily for validated recall. A bounded few cents of provider/model
spend can be justified when it prevents permanently missing a useful source.

### Recurring jobfinding

Repeated connector execution must optimize the balance between LLM spend and
missed opportunity cost.

Track at least:

- provider/model cost per validated rescued opportunity;
- validated incremental recall by stage;
- estimated missed-opportunity rate from a small shadow sample of deterministic rejects;
- escalation rate per stage;
- duplicate provider/model calls on unchanged evidence (target: `0`);
- stage latency and provider failure rate.

A static monthly money cap is a safety boundary, not the primary routing rule.
The preferred routing decision is expected incremental opportunity value versus
expected incremental provider/model cost.

## Stage evidence contract

Each executing stage should eventually emit:

- booster surface;
- stage name;
- `attempted`;
- status (`completed`, `skipped`, `blocked`, `failed_closed`);
- reason code;
- provider/model request count;
- actual/estimated cost where available;
- input evidence fingerprint;
- produced hypothesis/evidence references;
- deterministic validation outcome;
- state-progress result;
- explicit `product_authority=false` for provider/model output.

A shared per-case progress ledger must prevent duplicate queries, URLs, evidence
fingerprints and unchanged retries across search and model stages.

## Promotion and smoke-test programme

Every new surface/stage follows:

```text
offline fixtures
-> live shadow smoke
-> bounded canary
-> controlled default
```

### Offline fixture minimums

Build a broad fixture set rather than a single-employer regression:

- positive examples;
- hard negatives and telemetry/navigation noise;
- ambiguous examples;
- adversarial/misleading labels and URLs;
- redirected and embedded routes;
- multiple ATS families and employer-owned boards;
- location/remote semantic variants;
- changed versus unchanged recurring evidence.

### Mandatory contract tests per stage

Prove at minimum:

1. deterministic success skips Tavily and all model stages;
2. Tavily success skips all model stages;
3. Tavily disabled continues to Luna;
4. missing key continues to Luna;
5. exhausted budget continues to Luna;
6. insufficient next-request budget continues to Luna;
7. provider-unavailable outcome cannot fabricate success and does not by itself block Luna;
8. Luna success stops Terra/Sol/max;
9. Luna miss + Terra success stops Sol/max;
10. Luna/Terra miss + Sol success stops max;
11. full model residual may reach Luna max;
12. no normal path reaches Pro mode;
13. a model hypothesis rejected by deterministic authority remains rejected;
14. one shared progress ledger prevents repeated query/URL/fingerprint work;
15. hard cost ceilings fail closed;
16. timeouts/provider errors remain observable;
17. unchanged recurring fingerprint produces zero provider/model calls;
18. changing the evidence hash or contract version invalidates the recurring semantic cache;
19. no provider/model stage owns a product write.

### Live shadow campaign

Before default promotion on a new semantic surface, run enough representative
real decisions to estimate incremental precision, recall and cost. The initial
planning target is at least 100 representative decisions where practical, but
evidence quality matters more than an arbitrary count and current evidence-driven
retry governance remains authoritative.

Measure each model's **incremental** value after earlier stages. A stronger model
is retained only if it provides validated marginal rescue at acceptable cost and
latency.

## Implementation sequence

1. **Slice 1 — pure policy and tests**
   - common surface/stage policy;
   - search-first ordering;
   - Tavily skip semantics;
   - empirical planning costs;
   - recurring fingerprint guard;
   - no provider/DB/product execution.

2. **Slice 2 — canonical origin integration**
   - replace current model-first origin ordering with the shared search-first policy;
   - preserve deterministic origin validation and shared progress ledger;
   - add explicit Tavily budget-state adapter and skip reasons;
   - run focused CI and bounded private runtime acceptance.

3. **Slice 3 — listing/ATS/detail shadow boosters**
   - integrate the common policy into the currently hardened listing/ATS/detail surfaces;
   - provider/model outputs remain shadow evidence initially;
   - promote only empirically useful stages.

4. **Slice 4 — recurring connector economics**
   - persist/reuse semantic evidence fingerprints;
   - unchanged evidence produces no provider/model request;
   - add missed-opportunity shadow sampling and cost/rescue ledger;
   - canary before wider controlled default.

## Current boundary

Slice 1 is intentionally side-effect free. The canonical production origin
cascade is not reordered merely by importing this policy module. Promotion of
the new order into the current origin controller belongs to Slice 2 after Slice
1's exact-head tests/CI are green.
