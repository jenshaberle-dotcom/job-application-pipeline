# F4A — Profile Fit Coverage

Status: QUALIFICATION

Base: canonical `main@f7ae7ec873d04fbbef4d61a7aa4257c23c00387b`
Target desktop release: `1.0.25`
PR: `#868`

## Goal
Every lifecycle-current canonical review job must expose either:

- an evidence-backed Candidate↔Job Profile Fit result; or
- explicit `insufficient_evidence`.

Preliminary role affinity remains a separate non-authoritative operator-orientation signal.

## Required factors
- geography / work model / commute;
- seniority;
- skills / capabilities;
- hard requirements.

## Authority
Candidate-side truth comes only from approved Candidate Facts. Job-side truth comes only from current authoritative vacancy evidence. Missing evidence is not negative evidence.

F4A does not create a new ranking score. `profile_fit_complete` means the fit decision is conclusive from evidence: either every required factor is evidence-backed and passes, or at least one required factor has conclusive negative evidence. `insufficient_evidence` always carries an `unknown` decision and must never be interpreted as negative fit.

Capability truth is accepted only from an active Candidate Fact capability review bound to the current approved profile hash, current assessment timestamp, current detail-evidence hash and currently approved referenced Candidate Facts. Geography/work-model/commute candidate policy may come only from approved, current `operator_preference` Candidate Facts using the bounded `profile-fit.*` tag vocabulary. Raw Candidate Fact statements, provenance references and preference-tag values do not leave the private Candidate Fact boundary.

## Product projection
The existing Product payload now exposes, per current job:

- `profile_fit_coverage_status`;
- `profile_fit_decision`;
- factor status and generic reason for geography/work-model/commute, skills/capabilities, seniority and hard requirements;
- explicit missing and failed factor names;
- no ranking, Top-5 or application authority.

The Control Center renders the F4A coverage/decision separately from both the preliminary Role Affinity preview and the existing Product score/gate. F4B ranking remains untouched.

## Real Product evidence
Exact-head real Product acceptance run `34719248796` on `9c7e9c5d8c00152f4c8e329608b3947036caf6e3` completed successfully on the RCC-backed Product database.

Observed current truth:

- current canonical jobs: `72`;
- assessment rows: `17`;
- approved Candidate Facts: `7`, all capability-class evidence;
- approved preference facts: `0`;
- approved boundary facts: `0`;
- exact-current capability reviews: `7`;
- hard filter: `6 passed`, `66 unknown`;
- current Profile Fit partition: `0 profile_fit_complete`, `72 insufficient_evidence`, `0 unclassified`;
- decisions: `72 unknown`, `0 failed`, `0 passed`.

The all-`insufficient_evidence` result is therefore the correct fail-closed outcome for the current Product database: no approved Candidate preference/boundary truth exists for geography/work-model/commute, so F4A must not invent a positive or negative Candidate↔Job fit. The acceptance also proves zero Candidate statements, provenance references or raw preference tags emitted and zero ranking/Top-5/application authority created.

Missing-factor counts in that proof:

- geography/work-model/commute: `72`;
- hard requirements: `66`;
- seniority: `65`;
- skills/capabilities: `65`.

## Boundaries
- preserve F3 lifecycle and canonical-vacancy identity truth;
- do not start F4B ranking work;
- do not introduce employer-specific fit logic;
- do not silently classify a current review job when required evidence is absent;
- keep `CR-F1-001` visible unless this package naturally touches and closes the fresh-company persistence path.

## Acceptance
A real Product coverage proof must reconcile all current review rows into exactly one of:

`profile_fit_complete | insufficient_evidence`

with zero silently unclassified current jobs, factor-level explanations, and explicit evidence coverage. Exact-head Full Suite, Ruff, React, Windows contracts, automatic v1.0.25 release/deploy, and installed operator acceptance are required before F4B.

The real Product acceptance requirement is satisfied for the implementation above. Final package acceptance remains conditional on exact-final-head CI/contracts, merge, immutable automatic `1.0.25` release, automatic local deploy, and installed operator acceptance.
