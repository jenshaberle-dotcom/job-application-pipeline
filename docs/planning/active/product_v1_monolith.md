# PRODUCT-V1-MONOLITH-001

Status: operator policy approved; runtime migration prepared  
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
→ approved ranking and hard-filter policy
→ Gold Top-5 serving
→ approved CV and base-letter manifest
→ review-safe application draft request
→ React Control Center through read-only JSON API
```

## Implemented repository surfaces

- migration `077_create_product_v1_monolith_foundation.sql`;
- migration `078_activate_product_v1_operator_policy.sql`;
- persistent exclusion-wave state and empty-wave constraint repair;
- deterministic, provider-free ranking domain;
- approved at-most-five, no-fill ranking policy;
- approved structured hard-filter policy;
- application source-document and request contracts;
- Gold Product V1 hard-filter, readiness, Top-5 and application-readiness views;
- integrated Product V1 runner;
- guarded atomic runtime migration script for migrations 077 and 078;
- read-only Product V1 API;
- React/TypeScript Control Center source;
- provider-free tests for policy, ranking, migration, API and frontend contracts.

## Approved Top-5 start policy

- at most five jobs;
- never fill the list with blocked or below-threshold jobs;
- minimum score: `70/100`;
- ML/profile direction: `40%`;
- Reliability potential: `25%`;
- Data/Data-Engineering focus: `20%`;
- origin/evidence quality: `15%`;
- otherwise comparable window: `3` score points;
- hybrid, commute and public-transport preferences may reorder jobs only inside that window;
- rank, overall score, component scores, reasons, uncertainties and missing information remain visible;
- all values are versioned V1 starting values and may be adjusted later by the operator.

## Approved hard-filter start policy

- actual requirements and evidenced capability fit take precedence over the advertised seniority label;
- a Senior/Lead/Principal-labelled vacancy remains eligible when the requirements fit;
- a Junior-labelled vacancy with Senior/Lead/Principal-level requirements is excluded;
- permanent employment is required for authoritative Top-5 eligibility;
- accepted working languages are German and English;
- a required additional language fails the language hard filter;
- acceptable working time is 35–40 hours/week;
- an evidenced selectable range passes when it overlaps 35–40 hours;
- salary is negotiable and remains a soft signal;
- current salary target: approximately EUR 75,000 gross/year;
- missing required evidence remains manual-review-required rather than silently passing.

## Privacy boundary

The repository is public. The operator's current compensation is therefore not written to Git history. It remains private local runtime context. Migration 078 records only the approved negotiable target salary and the rule `current_compensation_storage = local_runtime_only`.

## Product decisions still open

This policy block deliberately does not decide:

- company, industry or role exclusions;
- maximum acceptable posting age;
- handling of unknown publication dates;
- the exact minimum evidence proving a concrete vacancy is still active;
- travel, customer-site or relocation treatment;
- operator review actions and lifecycle history;
- provider/model execution policy;
- ranking-change explanation between cycles.

These decisions remain visible in the Product Decision Register and are not invented by the implementation.

## Application assistant boundary

The assistant currently builds only a deterministic source manifest. It remains blocked until the operator provides and approves:

- a canonical base CV;
- a canonical base application letter.

No draft generation and no provider call are performed by this block. No application can be sent automatically.

## Runtime migration path

Default preflight is read-only:

```bash
python -m scripts.prepare_product_v1_runtime_migration
```

The prepared apply path is intentionally separate and requires the exact token:

```bash
python -m scripts.prepare_product_v1_runtime_migration \
  --apply \
  --approval-token apply_product_v1_runtime_migrations_077_078 \
  --applied-by jens
```

The script applies only migrations 077 and 078 in one database transaction. It refuses to bypass unresolved predecessor migrations and does not invoke StepStone, providers, sources, schedulers or application workflows.

## Runtime boundary

Repository merge does not:

- apply migrations 077 or 078 to the live database;
- call StepStone;
- apply company cooldowns;
- trigger a provider;
- register personal documents;
- start the API or React build;
- mutate a scheduler;
- activate a source;
- submit an application.

Each runtime effect remains a separate explicit operator action.

## Current operator stop point

After repository validation, the next runtime step is the separately approved execution of migrations 077 and 078. The application-assistant path additionally requires the canonical base CV and base application letter.
