# F4B Operator Gate 001 — Fit + Affinity authority

Status: **OPERATOR DECISION REQUIRED**

This is the first genuine F4B operator gate. The provider-free/read-only engineering work has been exhausted far enough that the next changes would alter Product authority rather than merely expose existing truth.

Evidence basis before this gate documentation:

- exact candidate head `969b218b51d1392ce1b05ac67b4423054287f444`;
- Pipeline CI `35002352454` — SUCCESS;
- Re-Entry `35002352154` — SUCCESS;
- real warm Product reconciliation `35002347221` — SUCCESS;
- artifact `10410505725`;
- 71 current Product jobs, 67 fresh same-Origin Affinity observations, 4 unavailable/404;
- 0 DB writes, 0 provider calls, 0 paid-provider spend.

No Combined-score formula is being approved at this gate. Current Fit completeness is insufficient for a meaningful arithmetic-vs-geometric comparison.

## Decision A — authoritative minimum quality threshold

**Recommendation: A1 — restore/canonicalize 70/100.**

A1. `70/100` remains authoritative, matching approved `PD-051`. The runtime `60` value is treated as historical DEMO-001 drift and must be corrected through normal Product policy migration/qualification.

A2. Explicitly supersede `PD-051` and approve `60/100` as the new authority.

A3. Leave the contradiction unresolved and freeze ranking mutation until a later Combined-score decision.

Why A1 is recommended:

- `PD-051` still says 70;
- the historical 60-cutoff path was explicitly designed to obtain five recommendations;
- current `PD-050` forbids quota filling and F4B explicitly makes Top 5 a derived projection;
- restoring 70 repairs governance without manufacturing Fit or changing the current zero-rankable truth.

## Decision B — what exact Candidate capability overlap may authorize

**Recommendation: B1 — strict positive-only evidence for the skill subfactor.**

B1. When current job-side bounded skill evidence exists and **every observed skill** is exactly backed by approved Candidate Fact capability evidence, JAP may mark only the **observed-skill subfactor** as passed. Partial overlap, zero overlap, missing job skills, or stale review bindings remain `unknown/manual_review_required`. Missing Candidate tags may **never** auto-fail Fit. Seniority, employment, hours, language and geography remain separate gates.

B2. Allow a majority rule such as `>=50%` exact observed-skill overlap to pass the skill subfactor. Zero/missing remains unknown; never auto-fail.

B3. Keep all capability Fit manual; exact overlap remains explanatory/prioritization evidence only and grants no Fit authority.

Current cohort impact for orientation:

- B1 would positively resolve only 3 current observed-skill subfactors;
- B2 would positively resolve 15;
- B3 would resolve none automatically.

Why B1 is recommended:

- approved Candidate Fact capability tags are intentionally narrow, so absence is not negative evidence;
- the job-skill extractor is useful but not proven exhaustive enough for negative inference;
- B1 permits only a one-way positive claim that is directly evidenced and keeps every ambiguous case fail-closed;
- it is sufficient to validate the production plumbing without optimizing the rankable count.

The six stale historical `passed` reviews are **not** part of this choice: exact-head/revision discipline already forbids rebinding them automatically. They must remain stale until a fresh review or newly approved deterministic authority resolves them.

## Decision C — role of the existing PD-052 score in F4B

**Recommendation: C1 — approve PD-052 components/weights as the initial Affinity authority, independent of Fit gates.**

C1. The existing deterministic components and approved weight vector (`40% profile direction / 25% reliability / 20% data / 15% evidence quality`) become the F4B **Affinity/desirability** score. It answers only `Will ich diesen Job?` and is calculated independently of Candidate Fit/hard-filter status. It may not override a hard Fit conflict. A fresh same-Origin but not-yet-persisted detail revision may be shown as provisional Affinity evidence but must be persisted/requalified before authoritative Combined ranking.

C2. Keep PD-052 only as the legacy ranking score and design a new Affinity rubric before F4B continues.

C3. Keep Affinity read-only/non-authoritative throughout F4B and use it only after full Candidate Fit is known.

Why C1 is recommended:

- the current deterministic rubric already measures the desirability/direction dimensions F4B calls Affinity;
- its weights still exactly match approved PD-052;
- fresh real-cohort evidence exists for 67/71 jobs;
- separating calculation from Fit gates fixes the current architecture mismatch without inventing a new scoring model during the freeze campaign;
- later operator feedback or learned methods can improve Affinity without blocking the current freeze.

## What is already decided and is not being reopened

- `PD-050`: Top 5 means at most five; no fill.
- Explicit hard-filter conflict remains blocking.
- Unknown evidence is not a midpoint and is not silently positive.
- Hannover Re 20h/week and fixed-term examples are true negative hard-gate evidence.
- Existing `PD-020..023` geography/work-model preferences remain the authority; current geography unknowns are a technical evidence/materialization problem, not a request for new preferences.
- No employer-specific exception, ML/LLM ranking authority, automatic application, or automatic email action is authorized.

## After operator decision

If the operator approves `A1 + B1 + C1`, the next engineering slice is deterministic and bounded:

1. record the decisions in the Product Decision Register;
2. correct the runtime quality threshold to 70 through a new migration/qualification path;
3. make PD-052 Affinity independent of Fit gates while preserving the score breakdown/explanations;
4. implement the B1 positive-only observed-skill subfactor and leave every other capability case unknown;
5. project existing PD-020..023 geography semantics from generic job-location evidence without inventing missing commute facts;
6. invalidate/supersede stale capability reviews rather than rebinding them;
7. rerun the current cohort and only then determine whether enough complete Fit rows exist to compare Combined-score formulas.

If another option is selected, implement exactly that authority instead. No release/merge is authorized merely by creating this gate document.