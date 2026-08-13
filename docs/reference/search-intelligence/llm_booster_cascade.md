# LLM-BOOST-001 — Search-first semantic booster cascade

Status: implementation contract
Authority: Issue #522

## Purpose and authority

LLM-BOOST-001 adds bounded semantic generalization where additional deterministic special cases stop scaling. It does not replace the deterministic pipeline and provider/model output never becomes product authority.

Canonical escalation order:

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

`Pro` is excluded from the normal cascade. The accepted origin residual campaign measured zero additional rescues from Pro+max at materially higher cost and latency.

Provider/model stages may propose URLs, ATS board roots, detail candidates, semantic fields with evidence, repair classifications and bounded next diagnostics. They may not directly establish employer identity, employer-to-ATS authority, concrete-detail truth, gate passes, source activation, lifecycle truth, ranking authority or application actions.

## Why Tavily comes before reasoning

Tavily acquires missing external information; Luna/Terra/Sol/max reason over available evidence. When external information is missing, search therefore precedes additional reasoning.

Tavily is first provider escalation where search is applicable, but it is never a prerequisite for the later model stages.

| Tavily state | Search action | Later model cascade |
|---|---|---|
| `available` | eligible within budget | continue if unresolved |
| `disabled` | skip | continue |
| `missing_key` | skip | continue |
| `budget_exhausted` | skip | continue |
| `insufficient_budget_for_next_request` | skip | continue |
| `provider_unavailable` | fail/skip closed | continue if safety permits |
| `unknown` | skip closed | continue |

No Tavily state may fabricate success or block Luna merely because search budget or provider availability is absent.

## Booster surfaces

### Origin discovery

Deterministic company/career-origin hypotheses remain first. Tavily is normally applicable after a deterministic miss. Every provider/model URL remains untrusted until the existing company-identity and career-origin validator accepts it.

### Listing discovery

Deterministic DOM, link, structured metadata, iframe and redirect evidence remains first. Tavily is only eligible for a diagnosed external-information gap, not as a routine listing fetch replacement. Model interpretation does not establish employer authority.

### ATS delegation

Deterministic employer-page-backed config, script and link evidence remains first. Models may separate telemetry/noise from plausible ATS board/root evidence. A provider hostname or brand alone never proves employer-to-ATS authority.

### Detail discovery

Deterministic concrete URL, ID and route evidence remains first. Models may propose unusual detail structures only after a bounded deterministic miss. Same-employer/source validation remains mandatory.

### Detail semantics

Known structured fields and deterministic term logic remain first. Models may extract role, seniority, skills, location and remote semantics with bounded evidence references. Existing product profile/geography contracts decide whether evidence is sufficient.

### Recurring connector

Recurring execution has a stricter economic boundary. An unchanged supported evidence fingerprint must cause zero provider/model calls.

Semantic cache identity:

```text
connector_id
+ source-local job identity or URL
+ normalized evidence hash
+ booster contract version
```

Changed evidence may become booster-eligible. Tavily remains limited to classified external-information/search-recall gaps; ordinary semantic ambiguity should proceed from deterministic parsing into the model cascade.

## Initial empirical cost model

Accepted 2026-08-12 GPT-5.6 origin campaigns plus the matching operator usage export give these planning means for the compact origin-hypothesis prompt family:

| Stage | Observed planning mean / call | Current hard ceiling |
|---|---:|---:|
| Luna medium | about `$0.00494` | `$0.01` |
| Terra medium | about `$0.01124` | `$0.02` |
| Sol medium | about `$0.02650` | `$0.05` |
| Luna max | about `$0.01538` on the small residual sample | `$0.05` |

These are planning observations, not universal future prices. Every new listing, ATS, detail or recurring semantic surface must run its own token/cost smoke campaign before default promotion.

The accepted 17-case origin sweep produced ordered validated lift of 10 Luna rescues, then 2 additional Terra rescues, then 1 additional Sol rescue. Four medium residuals remained and Luna max added one further rescue.

Using those observed stage-reach rates, expected model cost after an origin deterministic miss is about `$0.02098`, excluding Tavily. The nominal sum of all four model means is `$0.05806`; it is not the expected cascade bill because successful cases stop early.

## One-time versus recurring economics

One-time employer/origin/listing/ATS discovery creates reusable source capability, so validated recall dominates a few cents of bounded provider/model cost.

Recurring jobfinding must balance provider/model spend against missed opportunity cost. Track at least:

- cost per validated rescued opportunity;
- validated incremental recall per stage;
- estimated missed-opportunity rate from a small shadow sample of deterministic rejects;
- escalation rate per stage;
- duplicate provider/model calls on unchanged evidence, target `0`;
- latency and provider failure rate.

A monthly money cap remains a safety boundary. The preferred routing decision is expected incremental opportunity value versus expected incremental provider/model cost.

## Stage evidence contract

Every executing booster stage should emit its surface, stage, attempted/status/reason, request count, cost, input evidence fingerprint, produced evidence references, deterministic validation outcome, progress result and explicit `product_authority=false` for provider/model output.

One shared per-case progress ledger must prevent duplicate queries, URLs, evidence fingerprints and unchanged retries across Tavily and all model stages.

## Smoke and promotion programme

Every new surface/stage follows:

```text
offline fixtures
-> live shadow smoke
-> bounded canary
-> controlled default
```

The fixture set must cover positives, hard negatives/noise, ambiguous cases, adversarial labels/URLs, redirects/embedded routes, multiple ATS families, location/remote variants and changed versus unchanged recurring evidence.

Mandatory contracts include:

1. deterministic success skips Tavily and all models;
2. Tavily success skips all models;
3. disabled, missing-key, exhausted, insufficient-budget and unavailable Tavily continue to Luna;
4. Luna success stops Terra/Sol/max;
5. Terra success after Luna miss stops Sol/max;
6. Sol success after Luna/Terra misses stops max;
7. residual cases may reach Luna max but never normal Pro mode;
8. attractive model hypotheses rejected by deterministic authority remain rejected;
9. one progress ledger prevents repeated work;
10. hard cost ceilings and timeouts fail closed;
11. unchanged recurring evidence causes zero provider/model calls;
12. changed evidence hash or contract version invalidates the semantic cache;
13. no provider/model stage owns a product write.

Before default promotion on a new semantic surface, run a representative live shadow campaign large enough to estimate incremental precision, recall and cost; the initial planning target is at least 100 decisions where practical. Retain a stronger model only when it provides validated marginal rescue at acceptable incremental cost and latency.

## Implementation sequence

1. **Slice 1 — pure policy and tests:** common stage policy, search-first ordering, Tavily skip semantics, empirical planning costs, recurring fingerprint guard; no provider, database or product execution.
2. **Slice 2 — canonical origin integration:** reorder the current origin controller, preserve deterministic validation and shared ledger, add explicit Tavily budget-state handling, then run focused CI and bounded private runtime acceptance.
3. **Slice 3 — listing/ATS/detail shadow boosters:** integrate the shared policy into current hardening surfaces with no initial product writes; promote only empirically useful stages.
4. **Slice 4 — recurring connector economics:** reuse semantic fingerprints, add missed-opportunity sampling and cost/rescue evidence, then canary before wider controlled default.

## Current boundary

Slice 1 is side-effect free. The production origin cascade is not reordered merely by importing this policy module. Slice 2 may promote the new order only after Slice 1's exact-head tests and CI are green.
