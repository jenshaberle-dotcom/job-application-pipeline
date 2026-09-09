# JAP Current Re-Entry

Status: canonical current re-entry projection

Read this file from canonical `refs/heads/main` before continuing product work. `docs/current/README.md` remains useful general operational context, but this file is the sequencing authority where older text conflicts with it.

## Employer-Origin product authority

The Employer-Origin acquisition architecture is version-independent and has exactly one product admission path:

`candidate -> generic evidence-driven layers -> strict proof -> valid source -> generic_origin:<company_key> -> active recurring observation -> job plausibility gate -> Bronze -> Silver -> Gold -> Product -> Control Center`

The **generic evidence-driven layer model is the sole Employer-Origin source-validity truth**.

A source is valid when the current generic layer evaluation reaches `proof=PASS`. Every such source is eligible for product activation. V1, V2, V3, V4, V5 and V6 labels are historical engineering/audit checkpoints only. They are not independent product architectures, cohorts, promotion rules, activation authorities or fallbacks.

The following must not be used to admit or activate Employer-Origin sources:

- V1..V6 audit runners or fixed historical benchmark cohorts;
- DEMO-001 source/readiness workflows or demo evidence;
- historical materialized 36/65, 40/x or similar coverage cohorts;
- provider-specific one-off registry membership;
- legacy connector-validation/final-approval gate state as an alternative to generic `proof=PASS`.

Reusable provider/navigation/feed implementations may remain as capabilities composed **inside** the generic layered path. Their historical filename or origin does not grant them admission authority.

## Source admission is not Bronze admission

Source validity and current job quality are deliberately separate decisions.

1. `proof=PASS` admits and activates the source.
2. The active source may observe zero or more current job candidates.
3. Only minimally credible current job records are admitted to Bronze. At minimum the product record must preserve a concrete HTTPS detail URL, non-generic job title, employer identity, candidate identity and genuine generic-layer job proof lineage.
4. Zero Bronze-ready jobs is a valid successful observation for an active source and must not revoke source validity.

The generic recurring profile uses `*` only as a non-semantic execution trigger. Relevance/ranking vocabulary is a later product stage and must not be smuggled into source validity.

## Durable projection

`generic_employer_origin_active_sources` is the materialized current `proof=PASS` projection used to keep source activation inspectable. It is not a second admission system. Its schema only permits authority `generic_evidence_driven_layer_model` and `proof_state='pass'`.

Search profiles and candidate `active_controlled` state are downstream activation projections of the same current generic proof cohort.

## Current repository state

PR #846 (`P1: turn generic origin proof into bounded systematic search`) merged successfully to `main` as:

- merge SHA: `ee013d85152fa0f3dcb4e412fe5707b26976f2bc`
- proof head before squash merge: `a2f056eefbdc0445e1c751f305efe14fdc52c853`
- PR validation: green
- Pipeline CI run: `34355468312` — PASS
- systematic-search/read-only funnel run: `34355467837` — PASS
- systematic-search artifact: `p1-generic-origin-systematic-search`
- artifact digest: `sha256:d186f26b9f58708e108bf2a8acd194d7c4d26df296e4fad8ea71003c3273e8d5`

PR #846 added the bounded generic targeted-search runtime, query-semantic discrimination, local OSS detail evidence using pinned `extruct` plus bounded `trafilatura` fallback, normal `generic_origin:%` Silver-family plumbing, and a read-only stage-funnel audit that reuses the existing Bronze and Silver production functions.

## Current measured evidence

The latest completed read-only systematic-search proof on exact head `a2f056eefbdc0445e1c751f305efe14fdc52c853` produced:

### Search/discovery funnel

- active proof-valid Employer-Origin sources: `23`
- deterministic search surface detected: `9`
- query semantics proven: `3`
- query semantics unconfirmed-zero: `4`
- query semantics failed: `2`
- raw delivering sources: `5`
- accepted/query-proven delivering sources: `3`
- raw target jobs: `69`
- accepted/query-proven jobs: `67`
- HTTP requests: `647`

### Detail evidence

- detail evidence present: `67/67`
- structured schema.org `JobPosting`: `67/67`
- descriptions present: `67/67`
- structured location evidence: `20/67`
- explicit remote evidence: `0/67`
- live Trafilatura fallback cases: `0`

The current live evidence therefore strongly confirms `extruct` on the discovered cohort. `trafilatura` remains qualified only by its bounded fallback/unit contract until a real live fallback case naturally occurs. Do not manufacture a fallback case merely to raise coverage.

### Bronze -> Silver funnel

- Bronze admitted: `67/67`
- Bronze rejected: `0`
- accepted by normal Silver source selector: `67/67`
- Silver selector rejected: `0`
- Silver relevant if selected: `26/67`
- Silver successfully transformed: `26/26`
- Silver transformation failures: `0`
- Gold/Product readiness reached by this read-only audit: `0`
- Control Center reached by this read-only audit: `0`

Silver relevance reasons:

- `16` — `relevant_role_and_accessibility`
- `10` — `relevant_skills_and_accessibility`
- `30` — `missing_accessibility_signal`
- `11` — `missing_role_or_skill_signal`

The current evidence disproves the prior concern that naturally discovered Employer-Origin jobs lose required detail evidence at the Bronze -> Silver boundary. Once a query-proven job is reached in this cohort, the new local detail-evidence layer is sufficient for the existing Bronze and Silver production functions.

## Current bottleneck interpretation

The dominant measured gap is now **before detail extraction**, not after it:

`23 proof-valid sources -> 9 deterministic search surfaces -> 3 query-semantically proven sources`

The downstream reached-job path is currently healthy:

`67 query-proven -> 67 detail evidence -> 67 Bronze -> 67 Silver-selector eligible -> 26 relevant -> 26 transformed`

Do **not** start portal-specific hardening, company allowlists, vocabulary/taxonomy tuning, search-space expansion, provider introduction, or cosmetic location/remote extraction work merely to improve these counts before the first normal Gold -> Product -> Control Center E2E is proven.

## Effect authority

PR validation and the systematic-search qualifier remain read-only.

`.github/workflows/p1-generic-origin-product-activate.yml` remains the sole bounded Employer-Origin activation effect path for the source-admission cutover. It must use exact main, the verified local Product/PostgreSQL runtime, the generic proof projection, the normal `generic_origin` registry, normal ingestion and Bronze-admission verification. No demo workflow, V6 runner, manual fixed cohort or provider-specific registry path may substitute for it.

The next downstream proof must likewise reuse the normal persisted product path. A read-only audit must not fake Gold/Product/Control-Center success.

## Sole next action

Take at least one of the `26` real Silver-relevant results produced by the proven systematic-search path and drive it through the **unchanged normal persisted** downstream chain:

`query-proven search -> generic local detail evidence -> Bronze -> Silver -> Gold -> Product -> Control Center`

Success requires real persisted state and operator-visible Control Center evidence for the same job identity, with no special-case source/company path and no relaxed gate semantics.

Only after at least one such real E2E reaches Control Center should work return to the measured `3/23` query-semantics/search-surface gap. The first residual priority after E2E is generic search-surface/query-semantic generalization, not detail-extractor or vocabulary tuning.
