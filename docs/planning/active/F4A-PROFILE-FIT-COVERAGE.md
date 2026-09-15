# F4A — Profile Fit Coverage

Status: OPERATOR ACCEPTED / COMPLETE

Original shipped package: PR `#868`
Final corrective closure: F4A-R8
Immutable accepted desktop release: `1.0.32`
Accepted Product source: `ec2e411ad5240f38e3cc38ee7f76dbac369a8388`

## Goal

Every lifecycle-current canonical review job must expose either:

- an evidence-backed Candidate<->Job Profile Fit result; or
- explicit `insufficient_evidence`.

Preliminary role affinity remains a separate non-authoritative operator-orientation signal.

## Required factors

- geography / work model / commute;
- seniority;
- skills / capabilities;
- hard requirements.

## Authority

Candidate-side truth comes only from approved Candidate Facts. Job-side truth comes only from current authoritative vacancy evidence. Missing evidence is not negative evidence.

F4A does not create a ranking score. `profile_fit_complete` means the fit decision is conclusive from evidence: either every required factor is evidence-backed and passes, or at least one required factor has conclusive negative evidence. `insufficient_evidence` carries an `unknown` decision and must never be interpreted as negative fit.

The Product projection keeps Profile Fit separate from preliminary Role Affinity and from the existing Product ranking score. F4B owns the later decision on whether and how Fit may become ranking authority.

## Historical v1.0.25 rejection

The first installed F4A surface correctly failed closed but exposed insufficiently useful job-side metadata across real sources. That operator rejection triggered the corrective evidence-quality hardening rather than a UI-only patch.

The corrective direction remained generic and source-neutral:

`authoritative detail evidence -> structured/contextual semantics -> bounded deterministic fallback -> explicit unknown`

Employer-specific production truth exceptions remained forbidden.

## Final F4A-R8 closure

The final guarded operator-acceptance path requalified the current cohort through:

`Employer Origin -> Bronze evidence -> Silver requirement sidecar -> Product V1 -> Control Center`

Final evidence established:

- `70` current proposals accounted for;
- `41` Silver requirement sidecars needed refresh before the guarded Apply;
- post-Apply convergence reached `would_change_count = 0`;
- all reachable Product rows projected without extractor gap;
- coverage gate passed;
- zero legacy ambiguity;
- zero Silver -> Product/Control-Center projection loss;
- zero acceptance violations.

The exact accepted state was released as desktop `1.0.32` from `main@ec2e411ad5240f38e3cc38ee7f76dbac369a8388`. Release-triggered local deploy run `34970391624`, attempt `2`, completed successfully and proved the installed immutable identity plus bounded headless startup/rejection behavior.

## Installed operator acceptance — 2026-09-15

The operator accepted F4A on the installed `1.0.32` surface.

Observed acceptance outcome:

- requirement presentation is materially more coherent and useful;
- uncertainty/conflict remains visible instead of being silently converted into positive fit;
- the slice is directionally correct both semantically and visually;
- remaining imperfections do not justify extending F4A while larger frozen-campaign gaps remain.

Two residuals are deliberately carried:

- `#883`: About/version discoverability is missing; non-blocking UX debt for a later natural UI checkpoint.
- `#884`: Hannover Re exposes a visible Profile Fit conflict; use it as F4B calibration evidence. It does not reopen F4A unless investigation proves a confident false requirement assertion rather than a truthful fit conflict/unknown.

## Acceptance result

F4A is complete. F4B is unblocked.

The next package must not optimize for a larger rankable count or a filled Top 5. It must reconcile and improve decision quality while preserving the F4A truth boundary.

## Boundaries retained after closure

- preserve F3 lifecycle and canonical-vacancy identity truth;
- no employer-specific fit logic or metadata truth exceptions;
- no silent classification when required evidence is absent;
- Candidate Fact privacy and exact-current review binding remain unchanged;
- Profile Fit does not gain ranking authority merely because F4A is accepted;
- future ranking authority changes belong to F4B and require an explicit Product Decision.