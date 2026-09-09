# JAP Current Re-Entry

Status: canonical current re-entry projection

Read this file from canonical `refs/heads/main` before continuing product work. `docs/current/README.md` remains useful general operational context, but this file is the sequencing authority where older text conflicts with it.

## Employer-Origin product authority

The Employer-Origin acquisition architecture is now version-independent and has exactly one product admission path:

`candidate -> generic evidence-driven layers -> strict proof -> valid source -> generic_origin:<company_key> -> active recurring observation -> job plausibility gate -> Bronze`

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

## Current measured evidence

The last completed read-only generic product run before this authority cutover evaluated all 66 persisted Employer-Origin candidates and produced 23 `proof=PASS` sources:

- workflow run `34326006832`
- job `102383543763`
- evaluated candidates: `66`
- proof-pass sources: `23`
- database writes: `0`

This 23-source result is evidence, not a hard-coded cohort. Main activation must recompute the generic model and use the fresh resulting PASS set. Candidate-count/coverage improvement for the remaining sources is a separate hardening stream and must not block activation of the currently proven sources.

## Effect authority

PR validation remains read-only.

After the generic product architecture is merged to `main`, `.github/workflows/p1-generic-origin-product-activate.yml` is the sole bounded Employer-Origin activation effect path for this cutover. It must:

1. check out the exact main SHA;
2. use the verified local Product/PostgreSQL runtime;
3. apply the generic active-source projection migration fail-closed;
4. recompute the current generic proof cohort;
5. execute every proof-pass source through the normal `generic_origin` registry;
6. activate exactly the fresh proof-pass set and retire legacy Employer-Origin execution profiles;
7. run normal `generic_origin` ingestion;
8. verify that every persisted generic Bronze row passed the separate Bronze-admission gate.

No demo workflow, V6 runner, manual fixed cohort or provider-specific registry path may substitute for this chain.

## Current continuation

Complete PR #841 on exact-head CI/read-only proof. If green, merge it normally. Then let the automatic exact-main activation workflow execute on the trusted local Product runtime. Report the fresh source count, successful per-source observation runs, number of sources currently delivering Bronze-ready potential jobs, and Bronze row count.

Only after this activation/E2E boundary is proven should the separate residual work resume to improve generic coverage beyond the current proof-pass set.
