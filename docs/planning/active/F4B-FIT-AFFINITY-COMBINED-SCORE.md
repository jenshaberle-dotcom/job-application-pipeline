# F4B — Fit + Affinity Combined Decision Target

Status: ACTIVE / FROZEN CAMPAIGN NEXT PACKAGE

Issue authority: `#885`
Inherited calibration residual: `#884`

## Why F4B exists

F4B must improve decision quality, not merely populate a Top-5 view.

The operator-facing product should answer three distinct questions:

1. **Affinity / desirability — `Will ich diesen Job?`**
2. **Candidate<->Job Fit — `Passt dieser Job zu mir?`**
3. **Combined decision — `Wie gut ist dieser Job insgesamt fuer mich?`**

Top 5 is a downstream presentation projection over qualifying combined decisions. It is not an independent truth model and must never be quota-filled.

## Current authority and non-contradiction rule

`PD-052` remains the approved production ranking authority until explicitly superseded. Its current score uses profile/ML direction, Reliability potential, Data/Data-Engineering focus and origin/evidence quality.

F4B introduces no production score change merely by documenting this target. `PD-059` is proposed only.

The existing approved contracts remain binding throughout read-only calibration:

- `PD-050`: at most five, never fill with weaker/blocked jobs;
- `PD-051`: minimum overall quality `70/100` remains current authority;
- `PD-053`: hard-filter failure blocks authoritative ranking; required unknown evidence remains review-required;
- `PD-054`: missing required evidence blocks authoritative ranking rather than becoming a fabricated value;
- `PD-055` / `PD-056`: components, reasons, uncertainties and missing information remain visible.

A future combined-score decision may supersede or revise `PD-052` only after operator review of real-cohort evidence. It may not weaken `PD-050`, `PD-053` or `PD-054` as an accidental side effect.

## A — Affinity / desirability

Affinity represents whether the opportunity is strategically attractive to the operator. Candidate signals include:

- target role/profile direction;
- substantive ML / Data / Reliability content;
- work-model and commute preference where those are soft preferences rather than compatibility boundaries;
- future operator-reviewed preference signals when separately qualified.

Affinity is not evidence that the candidate satisfies vacancy requirements.

The existing Product ranking components are treated as the current production proxy for this side of the decision until F4B evidence justifies a revised model.

## B — Candidate<->Job Fit

Fit represents evidence-backed compatibility between the current candidate profile and the current authoritative vacancy.

At minimum F4B must account for:

- skills / capabilities;
- seniority / experience requirements;
- hard vacancy requirements;
- geography / work model / commute where those are actual compatibility boundaries rather than preferences.

A Fit value is authoritative only when the underlying required factors are sufficiently evidenced. Missing required factor evidence remains `unknown`; it is not silently mapped to a neutral midpoint.

A conclusive negative required factor remains a conflict. High Affinity cannot average that conflict away.

Fit score and Fit evidence coverage/confidence are separate concepts. A numeric Fit value must never hide weak evidence coverage.

## C — Combined decision score

A combined score is eligible only after:

- current authoritative vacancy truth is established;
- Employer-Origin authority is valid;
- hard filters have not failed;
- required Fit evidence is sufficient under the approved F4B contract;
- no blocking Candidate<->Job conflict exists.

The initial read-only comparison should include at least:

1. **Fit-dominant weighted arithmetic candidate**, initially explored as `60% Fit + 40% Affinity`;
2. **low-component-penalty candidate**, e.g. a weighted geometric combination, to test whether arithmetic averaging produces implausibly high totals when one component is weak.

These formulas are calibration candidates only. Neither is production authority before explicit operator approval.

## D — Top-5 projection

After currentness, authority, hard gates, evidence sufficiency and an approved combined score:

- sort eligible jobs by the approved combined decision score;
- apply the approved quality threshold;
- return at most five;
- leave slots empty when fewer jobs qualify.

F4B success is never measured by reaching five jobs.

## First read-only reconciliation

Before any ranking-authority mutation, produce one artifact covering every current Product review job with:

- canonical Silver/job identity;
- lifecycle/currentness;
- Origin authority;
- current Affinity/production score and components;
- Profile Fit coverage + decision;
- Profile Fit factor states, failed factors and missing factors;
- hard-filter status and reasons;
- current Product readiness/rankability;
- current Top-5 membership;
- candidate numeric Fit only where evidence supports it;
- Fit evidence coverage/confidence separately from Fit value;
- candidate combined-score variants where eligible;
- first exact exclusion/blocker reason.

The artifact must explicitly account for the Hannover Re conflict tracked in `#884` and classify it as one of:

- truthful conclusive negative Fit;
- insufficient/unknown evidence;
- generic extraction/calibration defect.

No Hannover-Re-specific production exception is allowed.

## Acceptance direction

F4B is ready for operator acceptance when the current cohort reconciles without silent gaps and the operator can inspect, per current job:

- `Will ich diesen Job?` — Affinity;
- `Passt dieser Job zu mir?` — Fit + evidence/unknowns;
- `Wie gut ist er insgesamt fuer mich?` — combined decision only when authoritative;
- exact exclusion reason when no combined decision is allowed.

Only then may the operator explicitly approve a production combined-score formula/threshold and supersede the relevant current ranking decision.

## Boundaries

- no provider/LLM ranking authority in this package unless separately qualified;
- no fabricated Fit score for unknown required evidence;
- no target rankable count;
- no Top-5 quota fill;
- no employer-specific scoring exception;
- no high Affinity overriding a hard Fit conflict;
- no change to frozen package order.

## Sole next action

Build and run the provider-free/read-only current-cohort reconciliation on the current accepted Product state. Use that evidence to identify the first population-level F4B blocker before changing ranking authority.