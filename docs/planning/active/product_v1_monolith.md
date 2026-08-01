# PRODUCT-V1-MONOLITH-001

Status: implementation in review  
Product character: A — Intent Locked  
Risk: repository implementation only; live actions remain operator-controlled

## Product outcome

Integrate the four approved Pipeline pillars into one coherent Product V1 path:

1. persistent, conservative StepStone company-discovery waves;
2. origin-gated Top-5 job serving;
3. source-grounded CV and application-letter assistance;
4. React Control Center in the Deep Ocean Intelligence style.

## Monolithic flow

```text
StepStone bounded company waves
→ employer-origin discovery and validation
→ concrete active Silver job
→ Product V1 assessment and eligibility gates
→ approved ranking policy
→ Gold Top-5 serving
→ approved CV and base-letter manifest
→ review-safe application draft request
→ React Control Center through read-only JSON API
```

## Implemented repository surfaces

- migration `077_create_product_v1_monolith_foundation.sql`;
- persistent exclusion-wave state and empty-wave constraint repair;
- deterministic, provider-free ranking domain;
- explicit operator-decision gate for ranking policy;
- application source-document and request contracts;
- Gold Product V1 readiness, Top-5 and application-readiness views;
- integrated Product V1 runner;
- read-only Product V1 API;
- React/TypeScript Control Center source;
- provider-free tests for product, wave, API and frontend contracts.

## Product decisions deliberately not invented

The implementation does not choose:

- exactly five versus at most five;
- minimum Top-5 quality threshold;
- final ranking weights;
- numeric definition of otherwise comparable jobs;
- handling of missing job information;
- seniority, language, salary, contract-type or experience hard filters;
- operator review actions;
- provider/model execution policy.

The ranking policy remains `operator_decision_required` until these required decisions are approved.

## Application assistant boundary

The assistant currently builds only a deterministic source manifest. It remains blocked until the operator provides and approves:

- a canonical base CV;
- a canonical base application letter.

No draft generation and no provider call are performed by this block. No application can be sent automatically.

## Runtime boundary

Repository merge does not:

- apply migration 077 to the live database;
- call StepStone;
- apply company cooldowns;
- trigger a provider;
- register personal documents;
- start the API or React build;
- mutate a scheduler;
- activate a source;
- submit an application.

Each runtime effect remains a separate explicit operator action.

## Operator stop point

After repository validation, the next product-shaping step requires operator input for:

1. the ranking-policy decisions listed above;
2. the base CV and base application letter.

Implementation must stop there rather than generating defaults or synthetic application facts.
