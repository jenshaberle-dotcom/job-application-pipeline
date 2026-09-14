# F4A-R2 — Operator-visible requirement evidence and coverage

Status: ACTIVE — installed v1.0.26 operator acceptance failed

Base: `main@458f7b132389b4ef10206fd34a8aa66a93a1c535`
Rejected installed release: `jap-winapp-desktop-v1.0.26`
Next immutable corrective release: `1.0.27`

## Operator finding — 2026-09-14

The installed v1.0.26 package passes its technical release/deploy chain but does **not** pass the F4A operator gate.

Observed visible behavior:

- the main `All jobs` detail surface still shows `Profile Fit coverage = insufficient evidence` and the F4A factor cards as `unknown` for the reviewed jobs;
- the structured/contextual job-requirement evidence hardened in F4A-Q is not projected as a normal operator-visible job-side evidence surface;
- therefore the operator cannot compare extracted seniority, skills, work model, languages, hours and other requirement facts against `Open original` from the normal product surface;
- the existing persisted structured refresh covered only the already-materialized assessment cohort, while the visible current review set is substantially larger;
- an all-`unknown` Candidate<->Job Profile Fit may still be correct when approved candidate preference/capability authority is missing, but it must not hide the separate job-side facts that are already known.

This is a product acceptance failure, not a reason to weaken fail-closed Profile Fit semantics.

## Root-cause split

Two truths must remain separate:

1. **Job-side requirement evidence** — what the authoritative Origin vacancy actually says. This can be projected when persisted evidence exists, with exact source provenance and explicit unknown/conflict states.
2. **Candidate<->Job Profile Fit** — whether those job requirements match approved Candidate Facts/preferences. This may remain `unknown` until candidate-side authority exists.

The current operator surface exposes (2) but not enough of (1). F4A-R2 closes that gap.

## Orlando finding

The Hannover Re `Financial Analyst` row with `Orlando | FL | 32801 | US` is **not a location-extraction false positive**. The Origin URL itself is Orlando-scoped and current external evidence identifies the vacancy as an Orlando, Florida role. The defect is **review/search-scope relevance**, not the displayed Origin location.

The installed `34%` preliminary affinity is also diagnostic evidence of the current bug. `build_review_fit_preview()` gives a role with no canonical target-role title signal a base `30`, adds `+2` for `commute_or_geography_review_required`, and adds `+2` for `active_confirmed`. `classify_geography()` excludes a row as `outside_germany` only when the structured `country` field is populated as non-German; a compound location carried in the `city` field can therefore fall through to the review-required-but-eligible bucket. `30 + 2 + 2 = 34` matches the installed Orlando row exactly.

Corrective rule:

- do not "repair" Orlando into Hannover;
- preserve the exact Origin location;
- make compound/structured country evidence available to the geography classifier before review-affinity eligibility is assigned;
- outside-Germany evidence must produce an explicit geography exclusion / zero review affinity rather than the permissive review-required fallback;
- approved candidate/search-scope policy remains the authority for narrower geography decisions inside Germany.

## Corrective scope

F4A-R2 must:

- use the structured/contextual requirement-evidence path for both initial Product assessment materialization and later detail refresh, not only a one-time corrective refresh;
- plan/materialize requirement evidence across the lifecycle-current Employer-Origin review cohort rather than only the small pre-existing assessment cohort;
- project persisted job-side requirement fields into the normal Product payload and `All jobs` detail surface;
- show at minimum employment type, required languages, weekly hours, work model, requirement seniority and extracted job skills when supported;
- distinguish `observed`, `unknown`, `conflict` and `not yet assessed` states;
- expose bounded evidence/provenance suitable for operator comparison without leaking private Candidate Facts;
- keep Candidate<->Job Profile Fit separate and fail-closed;
- keep ranking, Top 5 and application authority unchanged;
- classify geographic false positives using structured Origin geography plus approved geography/search-scope authority rather than rewriting correct Origin locations.

## Acceptance

Before the next operator gate:

- every lifecycle-current review job is reconciled to either a persisted requirement assessment or an explicit bounded reason why materialization is blocked;
- the operator can select a normal job in `All jobs` and compare visible job-side facts with `Open original` without using an internal diagnostic panel;
- supported fields show evidence-backed values; unsupported/conflicting fields remain visibly unknown;
- known false confident job-side metadata in the acceptance cohort is zero;
- Profile Fit may remain `insufficient_evidence` where candidate-side authority is absent, but the UI explicitly explains that this does not mean the job-side requirements are unknown;
- the Orlando Hannover Re case remains Orlando and is excluded from the bounded Germany review-affinity lane rather than receiving the current `34%` permissive fallback;
- exact-head Full Suite, Ruff, React, Windows contracts, real current-cohort proof, immutable release/deploy and installed operator acceptance all pass.

## Freeze sequence

Because v1.0.26 is already immutable and rejected, the next corrective package is F4A-R2 / `1.0.27`. Downstream package version targets shift by one and remain frozen until F4A is accepted:

`F4A-R2 / 1.0.27 -> F4B / 1.0.28 -> F4C / 1.0.29 -> F5 / 1.0.30 -> F6 / 1.0.31`

## Sole next action

First make structured/contextual requirement evidence durable in initial materialization and project persisted job-side facts into the normal Product payload/UI. In parallel, close the generic compound-location geography fallthrough proven by the Orlando case. Then run a real full-current-cohort materialization preflight to identify the remaining blocked source/lifecycle cases before any DB write. F4B remains blocked.
