# F4A-R2 / F4A-R3 — Operator-visible requirement evidence and coverage

Status: ACTIVE — installed v1.0.27 operator acceptance failed; F4A-R3 corrective gate in progress

Canonical base before F4A-R3: `main@c65ba002849e54cbb2203056d940191394a8a24b`
Rejected installed releases: `jap-winapp-desktop-v1.0.26`, `jap-winapp-desktop-v1.0.27`
Next immutable corrective release: `1.0.28`

## Operator findings — 2026-09-14

The installed v1.0.26 package passed its technical release/deploy chain but failed because the normal `All jobs` surface did not expose hardened job-side requirement evidence. F4A-R2 then reconciled the full lifecycle-current Employer-Origin cohort and released v1.0.27.

The installed v1.0.27 operator test proved a narrower remaining failure: the evidence is now persisted and visible inside the explanatory `Verified` / `Unknown / review` prose, but the normal job detail still does not expose dedicated vacancy-metadata fields. In the concrete Finanz Informatik `Data Platform Engineer (m/w/d)` case the UI visibly contained `Required languages: de`, `Weekly hours: 38 h/week` and structured/contextual `Python, Kubernetes` inside the explanation text while the normal metadata/profile cards still showed the corresponding operator dimensions as missing/unknown. The frontend projection was therefore incomplete, not the persistence layer.

The same real case also exposed two generic extraction issues:

- career-site shell/navigation text `Traineeprogramm` was incorrectly treated as the vacancy employment type although the vacancy title is not a trainee role;
- `Anteilige mobile Arbeit möglich` was visible Origin evidence for a partial mobile-work arrangement but was not mapped into the bounded work-model vocabulary.

These are product acceptance failures, not reasons to weaken fail-closed Profile Fit semantics.

## Root-cause split

Two truths must remain separate:

1. **Job-side requirement evidence** — what the authoritative Origin vacancy actually says. This can be projected when persisted evidence exists, with exact source provenance and explicit unknown/conflict states.
2. **Candidate<->Job Profile Fit** — whether those job requirements match approved Candidate Facts/preferences. This may remain `unknown` until candidate-side authority exists.

F4A-R3 closes the remaining projection gap without granting job-side metadata Candidate Fact, capability-fit, ranking, Top-5 or application authority.

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

F4A-R2/R3 must:

- use the structured/contextual requirement-evidence path for both initial Product assessment materialization and later detail refresh, not only a one-time corrective refresh;
- plan/materialize requirement evidence across the lifecycle-current Employer-Origin review cohort rather than only the small pre-existing assessment cohort;
- project persisted job-side requirement fields into the normal Product payload and `All jobs` detail surface;
- show at minimum employment type, required languages, weekly hours, work model, requirement seniority and extracted job skills when supported;
- distinguish `observed`, `unknown`, `conflict` and `not yet assessed` states;
- expose bounded evidence/provenance suitable for operator comparison without leaking private Candidate Facts;
- reject weak career-site shell-only employment-type signals such as unrelated `Traineeprogramm` for non-trainee vacancy titles;
- map narrow explicit partial-mobile-work wording to `hybrid`, while contradictions still resolve to `unknown`;
- keep Candidate<->Job Profile Fit separate and fail-closed;
- keep ranking, Top 5 and application authority unchanged;
- classify geographic false positives using structured Origin geography plus approved geography/search-scope authority rather than rewriting correct Origin locations.

## Current F4A-R3 proof

The exact-head real cohort preflight on the F4A-R3 branch found `70` candidates, `70` proposals, `0` blocked and `16` deterministic changes. All 16 changes were Finanz Informatik rows and included the expected `work_model`, evidence/prose and weak employment-type corrections; the operator-reported Silver `#579` was among them.

The guarded apply then persisted the current cohort with `70` persisted rows, `20` updated rows and `50` already-current rows, while retaining `3` explicit Origin-detail-unavailable cases. Candidate Fact reads, ranking authority, Top-5 authority, application authority and raw-HTML persistence remained zero. The immediate post-apply re-proof returned `70/70`, `0` blocked and `WOULD_CHANGE_COUNT=0`.

## Acceptance

Before the next operator gate:

- every lifecycle-current review job is reconciled to either a persisted requirement assessment or an explicit bounded reason why materialization is unavailable;
- the operator can select a normal job in `All jobs` and compare visible job-side facts with `Open original` without using an internal diagnostic panel or explanatory prose as the only carrier;
- supported fields show evidence-backed values; unsupported/conflicting fields remain visibly unknown;
- known false confident job-side metadata in the acceptance cohort is zero;
- Profile Fit may remain `insufficient_evidence` where candidate-side authority is absent, but the UI explicitly explains that this does not mean the job-side requirements are unknown;
- the Finanz Informatik acceptance example no longer presents unrelated career-site `Traineeprogramm` shell text as employment type and exposes supported partial mobile-work evidence conservatively as hybrid;
- the Orlando Hannover Re case remains Orlando and is excluded from the bounded Germany review-affinity lane rather than receiving the permissive review-required fallback;
- exact-head Full Suite, Ruff, React, Windows contracts, real current-cohort proof, immutable release/deploy and installed operator acceptance all pass.

## Freeze sequence

Because v1.0.27 is already immutable and rejected, the next corrective package is F4A-R3 / `1.0.28`. Downstream package version targets shift again and remain frozen until F4A is accepted:

`F4A-R3 / 1.0.28 -> F4B / 1.0.29 -> F4C / 1.0.30 -> F5 / 1.0.31 -> F6 / 1.0.32`

## Sole next action

Qualify the exact F4A-R3 head, merge only after the real cohort remains converged, publish/deploy immutable `1.0.28`, then repeat the installed operator test on the normal `All jobs` surface. F4B remains blocked until that operator gate passes.
