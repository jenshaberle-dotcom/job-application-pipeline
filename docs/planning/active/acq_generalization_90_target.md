# ACQ-GENERALIZATION-90 — deterministic full-population coverage target

Status: active
Date: 2026-08-28
Owner issue: #675

## Primary metric

The primary deterministic acquisition metric is no longer the historical 40-case
survivor cohort in isolation. It is strict functioning deterministic acquisition
coverage across the complete current distinct Employer-Origin candidate population.

At the 2026-08-28 market refresh:

- distinct current candidates: `N = 65`;
- connector-present cohort: `40/65`;
- strict functioning deterministic acquisition: `36/65 = 55.4%`;
- fresh out-of-sample candidates created from the market refresh: `10`;
- fresh candidates with a strict functioning deterministic connector: `0/10`.

Target:

`strict_functioning_candidates / all_current_distinct_candidates >= 0.90`

For `N = 65`, the minimum passing numerator is `59` (`59/65 = 90.8%`).
`58/65 = 89.2%` is not sufficient.

The denominator is dynamic. New valid Employer-Origin candidates increase `N`; the
target must not be met by suppressing, deleting, excluding, or reclassifying valid
candidates merely to reduce the denominator.

## What counts as success

A candidate counts in the numerator only when the deterministic stack can produce
unchanged strict genuine-job acquisition proof under the repository's existing
authority and side-effect boundaries. Merely having a generated connector, a
reachable career page, a plausible origin URL, provider recognition, or diagnostic
candidate evidence does not count.

The historical `36/40` remains a regression cohort and must not regress, but it is no
longer the primary coverage claim.

## First action — explain the 0/10 generalization failure before adding fixes

Do not start by rescuing the ten fresh employers individually. First classify why the
existing deterministic machinery produced `0/10` strict functioning connectors and
identify reusable root causes.

Required analysis dimensions:

1. employer-identity correctness at ingest;
2. deterministic origin candidate generation and request-budget ordering;
3. corporate alias / parent-brand / acronym / compact-domain handling;
4. first-party career-page -> job-portal delegation discovery;
5. already-supported ATS recognition/delegation that failed to receive authority;
6. server-rendered listing/detail extraction already covered by generic V4 classes;
7. client-rendered/API-backed listing classes not covered by the currently narrow
   Webpack/Next.js client-code delegation class;
8. cases with no current vacancy versus genuine acquisition capability gaps.

For every fresh case, record:

- observed market employer identity;
- persisted candidate identity;
- current first-party career/origin surface;
- known/provider family if observable;
- earliest failing deterministic stage;
- existing class that should have provided leverage, if any;
- reason that leverage did not fire;
- whether the cause generalizes to other current candidates.

Only after this root-cause matrix exists should implementation work be prioritized.
Priority is expected reusable lift across the 65-candidate population, not closure of
one named employer.

## Guardrails

- no company-specific success branches;
- no guessed tenant/opaque IDs;
- no proof or employer-authority weakening;
- no provider/LLM/Tavily requirement for the deterministic target;
- historical 40-case cohort remains a regression control;
- fresh market additions remain an out-of-sample generalization control.
