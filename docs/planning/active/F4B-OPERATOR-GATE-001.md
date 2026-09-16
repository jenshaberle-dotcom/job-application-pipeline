# F4B Operator Gate 001 — Fit + Affinity authority

Status: **OPERATOR DECIDED — A1 + C1 APPROVED; B/COMBINED DEFERRED**

Decision date: 2026-09-16

This is the first genuine F4B operator gate. The provider-free/read-only engineering work was exhausted far enough that the next changes would alter Product authority rather than merely expose existing truth.

Evidence basis before the operator decision:

- candidate gate head `24cdd0140b0fc8499ddffaa0e0ab61610b16b72c`;
- Pipeline CI `35002871935` — SUCCESS;
- Re-Entry `35002871734` — SUCCESS;
- real warm Product reconciliation `35002867627` — SUCCESS;
- 71 current Product jobs, 67 fresh same-Origin Affinity observations, 4 unavailable/404;
- 0 DB writes, 0 provider calls, 0 paid-provider spend.

The operator explicitly confirmed that the current cohort has **no authoritative Combined score** and that this is acceptable for the current freeze campaign. Numeric Candidate<->Job Fit automation, generic skill-extraction hardening and Combined-score calibration are deliberately deferred to the next freeze campaign rather than being forced through insufficient evidence now.

## Decision A — authoritative minimum quality threshold

**APPROVED: A1 — restore/canonicalize 70/100.**

`70/100` remains authoritative, matching approved `PD-051`. The runtime `60` value is historical DEMO-001 drift and must be corrected through the normal Product policy migration/qualification path.

Rationale:

- `PD-051` still says 70;
- the historical 60-cutoff path was explicitly designed to obtain five recommendations;
- `PD-050` forbids quota filling and F4B keeps Top 5 as an at-most projection;
- restoring 70 repairs governance without manufacturing Fit or changing the current zero-rankable truth.

## Decision B — Candidate capability overlap authority

**DEFERRED — no B option is approved for the current freeze campaign.**

B1 remains the preferred future direction: strict positive-only evidence may eventually allow an observed-skill subfactor to pass when every observed job-side skill is exactly backed by approved Candidate Fact capability evidence. However, the operator explicitly judged the current generic skill-extraction basis as not mature enough to promote even that rule into Product authority now.

Current evidence supporting deferral:

- B1 would positively resolve only 3 current observed-skill subfactors;
- B2 (`>=50%` exact overlap) would resolve 15, but the present extraction/candidate-tag coverage cannot justify that broader authority;
- missing Candidate tags remain non-negative evidence;
- the six historical `passed` capability reviews remain revision-stale and may not be rebound automatically.

Stable residual: **`F4B-FOLLOWUP-001`**.

The next freeze campaign should revisit capability Fit only after broader connector maturity and a larger real-job cohort provide a stronger generic extraction calibration set and/or enough evidence to qualify an ML-assisted skill understanding layer. Until then, partial/zero/missing capability overlap remains `unknown/manual_review_required` and grants no new Fit authority.

## Decision C — role of the existing PD-052 score in F4B

**APPROVED: C1 — PD-052 components/weights become the initial Affinity authority, independent of Fit gates.**

The existing deterministic components and approved weight vector (`40% profile direction / 25% reliability / 20% data / 15% evidence quality`) are the F4B **Affinity/desirability** score. It answers only `Will ich diesen Job?` and is calculated independently of Candidate Fit/hard-filter completion.

Boundaries:

- Affinity may not override a hard Fit conflict or missing required Fit evidence;
- a fresh same-Origin but not-yet-persisted detail revision may be shown only as provisional Affinity evidence until persisted/requalified;
- C1 does not create numeric Candidate Fit;
- C1 does not create a Combined score;
- C1 does not authorize ML/LLM ranking authority.

Rationale:

- the deterministic rubric already measures the desirability/direction dimensions F4B calls Affinity;
- its weights still exactly match approved PD-052;
- fresh real-cohort evidence exists for 67/71 jobs;
- separating Affinity calculation from Fit gates fixes the current architecture mismatch without inventing a new scoring model during the freeze campaign.

## Combined score — explicitly deferred

No arithmetic, geometric or other Combined-score formula is approved in this campaign. The current state of **0 authoritative Combined scores** is accepted repo/product truth, not an F4B blocker.

Combined calibration moves with `F4B-FOLLOWUP-001` to the next freeze campaign after capability/skill evidence is materially stronger. That later campaign may compare Fit-dominant arithmetic and stronger low-component-penalty formulas only on sufficiently evidenced real jobs.

## What remains unchanged

- `PD-050`: Top 5 means at most five; no fill.
- Explicit hard-filter conflict remains blocking.
- Unknown evidence is not a midpoint and is not silently positive.
- Hannover Re 20h/week and fixed-term examples remain true negative hard-gate evidence.
- Existing `PD-020..023` geography/work-model preferences remain authority; current geography unknowns are an evidence/materialization issue, not a request for new preferences.
- No employer-specific exception, ML/LLM ranking authority, automatic application, or automatic email action is authorized.

## Authorized current-campaign implementation

Only these two authority changes are authorized now:

1. **A1:** restore runtime `minimum_quality_score` to `70/100` through a new migration/qualification path without mutating historical migrations.
2. **C1:** make the existing PD-052 score available as explicit Affinity/desirability independent of Candidate Fit/hard-filter completion, preserving component breakdown, uncertainty and exact evidence binding.

Do **not** implement B1, capability auto-fit, skill-extraction expansion, numeric Fit or Combined scoring in this freeze campaign.

After A1+C1 exact-head qualification, the normal package flow remains merge -> immutable release -> automatic local deploy -> installed operator acceptance. `F4B-FOLLOWUP-001` must remain carried into the next freeze campaign and must not block F4C/F5/F6 merely because Combined scoring is absent.