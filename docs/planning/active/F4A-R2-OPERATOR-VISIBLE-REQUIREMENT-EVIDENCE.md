# F4A-R2 / F4A-R3 — Operator-visible requirement evidence and coverage

Status: ACTIVE — installed v1.0.27 operator acceptance failed; F4A-R3 release held for source-to-Silver semantic hardening

Canonical base before F4A-R3: `main@c65ba002849e54cbb2203056d940191394a8a24b`
Rejected installed releases: `jap-winapp-desktop-v1.0.26`, `jap-winapp-desktop-v1.0.27`
Next immutable corrective release: `1.0.28` — **do not publish until the source-to-Silver coverage gate below passes**

## Operator findings — 2026-09-14

The installed v1.0.26 package passed its technical release/deploy chain but failed because the normal `All jobs` surface did not expose hardened job-side requirement evidence. F4A-R2 then reconciled the full lifecycle-current Employer-Origin cohort and released v1.0.27.

The installed v1.0.27 operator test proved a narrower visible failure: evidence was persisted and visible inside explanatory `Verified` / `Unknown / review` prose, but the normal job detail still did not expose dedicated vacancy-metadata fields. In the concrete Finanz Informatik `Data Platform Engineer (m/w/d)` case the UI visibly contained `Required languages: de`, `Weekly hours: 38 h/week` and structured/contextual `Python, Kubernetes` inside the explanation text while the normal metadata/profile cards still showed the corresponding operator dimensions as missing/unknown.

The same real case exposed two generic extraction issues:

- career-site shell/navigation text `Traineeprogramm` was incorrectly treated as the vacancy employment type although the vacancy title is not a trainee role;
- `Anteilige mobile Arbeit möglich` was visible Origin evidence for a partial mobile-work arrangement but was not mapped into the bounded work-model vocabulary.

The follow-up source-path review after that operator test found a broader architectural gap: the frontend projection is only the secondary bottleneck. The primary remaining bottleneck is loss/duplication between generic connector detail evidence, Bronze and Silver.

These are product acceptance failures, not reasons to weaken fail-closed Profile Fit semantics.

## Root-cause split

Two truths must remain separate:

1. **Job-side requirement evidence** — what the authoritative Origin vacancy actually says. This can be projected when persisted evidence exists, with exact source provenance and explicit unknown/conflict states.
2. **Candidate<->Job Profile Fit** — whether those job requirements match approved Candidate Facts/preferences. This may remain `unknown` until candidate-side authority exists.

F4A-R3 must close both the semantic transport gap and the operator projection gap without granting job-side metadata Candidate Fact, capability-fit, ranking, Top-5 or application authority.

## Confirmed bottleneck — connector/Bronze -> Silver -> Product

The repository already has a stronger generic local extraction layer than the current Product path uses:

- `src/connectors/generic_job_detail_evidence.py` uses pinned local OSS only: `extruct` for schema.org JSON-LD **and Microdata**, plus `trafilatura` as bounded main-text fallback;
- that generic layer can project title, company, description, structured locations, applicant locations, remote/workplace evidence, employment types, skills, date/validity and vacancy identifiers into bounded Bronze `raw_data.job` / `detail_evidence` without persisting raw HTML;
- these libraries are normal project dependencies/runtime assets, not remote providers or external services.

The current Silver contract then drops most of that semantic payload. `SilverJobRepository` persists the canonical identity/location/publication fields (`title`, `company`, `city`, `country`, publication date, canonicalization fields, etc.), but no durable normalized requirement-evidence contract for skills, employment type, work model, languages, hours, requirement seniority or the generic parser/provenance payload.

F4A consequently reparses the public Origin detail later at Product time. That path currently uses the in-repo deterministic semantics layer only for `skills` and `remote`; employment type, languages, weekly hours and requirement seniority still rely primarily on the flat assessment extractor. Its structured parser also covers JSON-LD only, while the established generic connector parser already supports JSON-LD and Microdata through `extruct`.

Therefore the current failure is **not primarily that most sources are unreadable**. The stronger generic connector evidence is not being carried through Silver as first-class normalized evidence, and Product re-extraction only partially recreates it. The dedicated frontend projection added in F4A-R3 is necessary, but it cannot recover fields that were lost or never normalized upstream.

## Current real-cohort signal

The guarded current-cohort proof covers `70` operator-visible jobs with `0` hard blockers. On the current Product reparse path:

- `65/70` have at least one verified requirement line;
- `36/70` expose a JSON-LD `JobPosting` to the lightweight Product parser;
- `39/70` produce at least one extracted job skill;
- `3/70` have explicit current Origin-detail-unavailable state;
- the post-apply cohort is converged (`WOULD_CHANGE_COUNT=0`).

This proves that most current Origins are reachable and yield some evidence, but it does **not** prove adequate field completeness for job-side fit. It also shows why frontend-only acceptance would be premature: roughly half the cohort does not expose JSON-LD to the current Product parser, while the already-established generic connector layer has broader structured parsing plus bounded main-text fallback.

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

- make generic connector/detail evidence a durable normalized Silver-side requirement-evidence contract instead of discarding it and reconstructing only part of it later;
- reuse the existing local `extruct` / `trafilatura` evidence path and preserve parser family, field status and bounded provenance without persisting raw HTML;
- use source-family/document contracts only when reusable across employers/ATS families; employer-specific truth exceptions remain forbidden;
- classify missing metadata as `source_absent`, `extractor_gap`, `conflict`, `origin_unavailable` or observed evidence instead of collapsing all missing states into one `unknown` bucket;
- use the structured/contextual requirement-evidence path for initial Product assessment materialization and later detail refresh;
- plan/materialize requirement evidence across the lifecycle-current Employer-Origin review cohort rather than only the small pre-existing assessment cohort;
- project persisted job-side requirement fields into the normal Product payload and `All jobs` detail surface;
- show at minimum employment type, required languages, weekly hours, work model, requirement seniority and extracted job skills when supported;
- expose bounded evidence/provenance suitable for operator comparison without leaking private Candidate Facts;
- reject weak career-site shell-only employment-type signals such as unrelated `Traineeprogramm` for non-trainee vacancy titles;
- map narrow explicit partial-mobile-work wording to `hybrid`, while contradictions still resolve to `unknown`;
- keep Candidate<->Job Profile Fit separate and fail-closed;
- keep ranking, Top 5 and application authority unchanged;
- classify geographic false positives using structured Origin geography plus approved geography/search-scope authority rather than rewriting correct Origin locations.

## Coverage gate before long-tail deferral

The operator explicitly accepts a bounded long tail at the end of the freeze path, but not a system where most missing metadata is merely hidden behind `unknown`.

Before F4A can pass and the residual long tail can move into a later observation/classification campaign:

- every current review job must have an explicit parser/evidence outcome (`structured`, `bounded_text`, `source_absent`, `extractor_gap`, `conflict` or `origin_unavailable`);
- at least **80% of reachable current jobs** must be covered without a known `extractor_gap` for F4A-relevant facts that are actually stated by the authoritative Origin; facts genuinely absent from the source do not count as parser failures;
- known false-confident canonical metadata in the acceptance cohort remains `0`;
- residual `extractor_gap` rows must be grouped by reusable source/document family and carried as an explicit long-tail backlog, not silently accepted as generic `unknown`;
- the Product/UI must consume the Silver-side normalized evidence rather than depending on a separate weaker reparse to reconstruct the same truth.

The first full layer-loss audit may tighten this threshold if the reachable cohort proves substantially more parseable, but it may not weaken it below an operator-meaningful majority merely to unblock F4B.

## Current F4A-R3 proof

The exact-head real cohort preflight on the F4A-R3 branch found `70` candidates, `70` proposals, `0` blocked and `16` deterministic changes. All 16 changes were Finanz Informatik rows and included the expected `work_model`, evidence/prose and weak employment-type corrections; the operator-reported Silver `#579` was among them.

The guarded apply then persisted the current cohort with `70` persisted rows, `20` updated rows and `50` already-current rows, while retaining `3` explicit Origin-detail-unavailable cases. Candidate Fact reads, ranking authority, Top-5 authority, application authority and raw-HTML persistence remained zero. The immediate post-apply re-proof returned `70/70`, `0` blocked and `WOULD_CHANGE_COUNT=0`.

That proof demonstrates deterministic convergence of the current corrective parser, not sufficient semantic coverage. It is therefore not release authority for `1.0.28`.

## Acceptance

Before the next operator gate:

- the source-to-Silver coverage gate above passes on the real current cohort;
- every lifecycle-current review job is reconciled to either persisted normalized requirement evidence or an explicit bounded reason why the field/source cannot currently be normalized;
- the operator can select a normal job in `All jobs` and compare visible job-side facts with `Open original` without using an internal diagnostic panel or explanatory prose as the only carrier;
- supported fields show evidence-backed values; unsupported/conflicting fields remain visibly classified rather than falsely asserted;
- known false confident job-side metadata in the acceptance cohort is zero;
- Profile Fit may remain `insufficient_evidence` where candidate-side authority is absent, but the UI explicitly explains that this does not mean the job-side requirements are unknown;
- the Finanz Informatik acceptance example no longer presents unrelated career-site `Traineeprogramm` shell text as employment type and exposes supported partial mobile-work evidence conservatively as hybrid;
- the Orlando Hannover Re case remains Orlando and is excluded from the bounded Germany review-affinity lane rather than receiving the permissive review-required fallback;
- exact-head Full Suite, Ruff, React, Windows contracts, real current-cohort proof, immutable release/deploy and installed operator acceptance all pass.

## Campaign sequencing

There is no later frozen package that legitimately owns this semantic extraction gap. F4C is source-health/operator-observability work, not source-to-Silver vacancy semantics. Carrying the current gap past F4A would therefore make the F4A acceptance false.

The version/freeze order remains:

`F4A-R3 / 1.0.28 -> F4B / 1.0.29 -> F4C / 1.0.30 -> F5 / 1.0.31 -> F6 / 1.0.32`

but F4B remains frozen until F4A-R3 includes the generic source-to-Silver hardening and passes the coverage gate. Only the bounded residual long tail may be deferred after that gate passes.

## Sole next action

Do **not** publish `1.0.28` yet. Run a read-only layer-loss audit across the full current review cohort that compares, per job/source family and field, generic connector/Bronze `detail_evidence` -> Silver -> Product assessment -> operator payload. Then implement the smallest generic Silver requirement-evidence projection that preserves the established `extruct`/`trafilatura` evidence and provenance, make Product consume that normalized Silver truth first, and rerun the cohort coverage gate. F4B remains blocked.
