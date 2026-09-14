# F4A — Profile Fit Coverage

Status: OPERATOR ACCEPTANCE FAILED / CORRECTIVE HARDENING REQUIRED

Original shipped package: PR `#868`
Immutable desktop release: `1.0.25`
Released product SHA: `948864965e282f6de4f95d1808d6c40e654b7bd6`
Corrective target desktop release: `1.0.26`

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
The Product payload exposes, per current job:

- `profile_fit_coverage_status`;
- `profile_fit_decision`;
- factor status and generic reason for geography/work-model/commute, skills/capabilities, seniority and hard requirements;
- explicit missing and failed factor names;
- no ranking, Top-5 or application authority.

The Control Center renders the F4A coverage/decision separately from both the preliminary Role Affinity preview and the existing Product score/gate. F4B ranking remains untouched until F4A is operator accepted.

## Shipped v1.0.25 evidence
The original exact-head Product acceptance run `34719248796` proved the fail-closed projection contract before release.

Observed truth at that proof point:

- current canonical jobs: `72`;
- assessment rows: `17`;
- approved Candidate Facts: `7`, all capability-class evidence;
- approved preference facts: `0`;
- approved boundary facts: `0`;
- exact-current capability reviews: `7`;
- hard filter: `6 passed`, `66 unknown`;
- current Profile Fit partition: `0 profile_fit_complete`, `72 insufficient_evidence`, `0 unclassified`;
- decisions: `72 unknown`, `0 failed`, `0 passed`.

Missing-factor counts in that proof:

- geography/work-model/commute: `72`;
- hard requirements: `66`;
- seniority: `65`;
- skills/capabilities: `65`.

The all-`insufficient_evidence` result was correct for the available Candidate-side truth and proved that missing evidence was not silently turned into negative fit. It did not prove that the upstream job-requirement extraction was semantically useful enough for an operator.

Release/deploy evidence is also complete: v1.0.25 was published from immutable source `948864965e282f6de4f95d1808d6c40e654b7bd6` and automatic local deploy run `34779970878` installed exactly that release successfully.

## Installed operator finding — 2026-09-14
The installed v1.0.25 UI and contract behave technically as intended, but F4A is **not operator accepted**.

Observed product gap:

- factor labels and status mechanics are present;
- the underlying job metadata for seniority, skills/capabilities and related hard requirements is not yet semantically reliable/useful enough across real vacancy sources;
- therefore the current Profile Fit surface can be technically correct while still being poor decision support;
- the low `rankable` count must be treated as an observation, not a target. Correct evidence quality may increase, decrease or leave that count unchanged.

This is not deferred as unrelated scope. The original F4A contract explicitly requires normalized job requirements from current authoritative vacancy evidence. The corrective work therefore remains inside F4A and blocks F4B.

## F4A-Q — Job Requirement Evidence Quality Hardening
The corrective slice must improve job-side evidence quality without employer-specific production exceptions.

Evidence understanding is layered, source-neutral and evidence-preserving:

1. prefer authoritative structured vacancy metadata when present (for example exact ATS/schema fields with provenance);
2. preserve semantic section/context information from the authoritative vacancy detail instead of flattening the whole page into one undifferentiated string;
3. use bounded deterministic phrase extraction only as fallback where the field meaning is unambiguous;
4. treat conflicting, context-poor or unsupported evidence as `unknown` rather than forcing a canonical value;
5. retain exact evidence references/provenance for every asserted field so an operator can inspect why a value exists.

Source-family understanding is allowed where it represents a reusable document/ATS contract. Employer-specific exceptions, company allowlists and UI-only repairs are not authority.

The existing detail-refresh path must continue to invalidate stale downstream human/capability/ranking decisions when authoritative vacancy evidence changes, and the corrected extraction must replay through the same Bronze/Silver/Gold/Product path.

## Corrective acceptance
F4A is accepted only after all of the following hold on the final exact package head:

- a representative real-source cohort covers the source families actually present in the current Product review set;
- extracted seniority, work model, employment type, languages, weekly hours and other F4A-relevant requirement evidence are inspected against their authoritative Origin evidence;
- every asserted canonical field is provenance-backed; ambiguous/conflicting cases remain explicit `unknown`;
- known false confident metadata in the acceptance cohort is zero at sign-off;
- current review rows still reconcile completely into `profile_fit_complete | insufficient_evidence` with zero silently unclassified jobs;
- Candidate Fact privacy and authority boundaries remain unchanged;
- ranking/Top-5/application authority remains unchanged;
- exact-head Full Suite, Ruff, React, Windows contracts and real Product proof pass;
- immutable automatic `1.0.26` release and automatic local deploy pass;
- installed operator acceptance explicitly passes.

## Boundaries
- preserve F3 lifecycle and canonical-vacancy identity truth;
- do not start F4B ranking work before F4A-Q is accepted;
- do not introduce employer-specific fit logic or employer-specific metadata truth exceptions;
- do not optimize for a larger rankable count;
- do not silently classify a current review job when required evidence is absent;
- keep `CR-F1-001` visible unless this package naturally touches and closes the fresh-company persistence path.

## Sole next action
Inventory the current Product review cohort by source family and compare existing extracted requirement fields against authoritative vacancy evidence. Use that evidence audit to implement the smallest generic/section-aware extraction hardening required for semantic correctness, then rerun the full F4A acceptance chain for target `1.0.26`.
