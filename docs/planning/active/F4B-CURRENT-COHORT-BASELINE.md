# F4B current-cohort baseline — 2026-09-15

Status: READ-ONLY EVIDENCE COMPLETE / OPERATOR GATE READY

Canonical campaign authority remains `main@35224c9b8351a3a260ba5d5e51236d61bb7ed8f5`. Active candidate is Draft PR `#888` on `agent/f4b-readonly-cohort`. Nothing in this branch changes Product ranking, Fit, hard-filter, Top-5 or application authority.

## Exact-head evidence before operator-gate documentation

Exact implementation/evidence head:

`969b218b51d1392ce1b05ac67b4423054287f444`

- Pipeline CI `35002352454`: **SUCCESS** — Full Suite, Ruff, governance/CI contracts and React build.
- Re-Entry identity `35002352154`: **SUCCESS**.
- Warm Product read-only reconciliation `35002347221`: **SUCCESS**.
- Evidence artifact `10410505725`: three bounded read-only reports, one-day retention.
- Provider calls: `0`; DB writes: `0`; paid spend: `$0.00`.

## Current Product funnel

The Product payload has **71** `active_confirmed` Silver identities, all with `origin_validation_status=validated`.

| Gate or state | Current count |
|---|---:|
| Profile Fit `unknown` / insufficient evidence | 69 |
| Profile Fit `failed` / conclusive negative hard requirement | 2 |
| Product hard-filter evidence required | 69 |
| Product blocked hard filter | 2 |
| Current Top-5 members | 0 |
| Evidence-backed numeric Fit scores | 0 |
| Authoritative Combined-score candidates | 0 |

The two negative Fit rows are real hard-requirement conflicts, not extraction defects. Hannover Re Silver `599` explicitly states 20 hours/week and conflicts with the approved 35–40h requirement. Silver `600` explicitly states fixed-term employment and conflicts with the approved permanent-employment requirement. High Affinity may not override either conflict.

## Capability evidence / stale review truth

The privacy-bounded operator packet compared approved Candidate Fact capability tags with current public job-side skill evidence in memory and emitted only counts/coverage, never Candidate Fact statements, private tags, fact keys, provenance or review rationales.

Current capability-review binding:

- `0` exact-current active capability reviews;
- `6` active reviews are stale after assessment/detail revision drift and may not be rebound automatically;
- `65` jobs have no active capability review.

Current public skill evidence:

- `49` jobs expose observed bounded job skills;
- `22` have no usable current skill list (`source_absent`, unavailable or missing);
- `3` jobs have all observed skills exactly backed by approved Candidate Fact capability evidence;
- `29` have partial exact overlap;
- `17` have observed skills but zero exact overlap.

This evidence is asymmetric. Missing Candidate tags and imperfect job-skill recall cannot prove a negative capability Fit. Exact overlap is useful positive evidence, but partial/zero/missing overlap must remain unknown unless separately reviewed.

## Geography/work-model truth

No new operator preference is required here. Approved `PD-020..023` already define the Product boundary: Germany-based remote is admissible; regional hybrid/onsite roles require realistic commute evidence, generally up to ~45 minutes each way; hybrid is a soft preference rather than a hard gate.

Read-only projection currently resolves `9` jobs as geography-compatible. `62` remain unknown because job-side evidence is incomplete: `45` lack a projected country, `12` require commute evidence for a regional role, and `5` have unresolved work model. This is technical evidence/materialization work, not permission to invent a new preference.

## Fit-independent Affinity truth

The historical ranking runner calculated the PD-052 components only after Capability Fit and hard filters had passed. That made current Affinity appear empty even though Affinity semantically answers a separate question: `Will ich diesen Job?`

The read-only F4B Affinity reconciliation therefore applies the existing deterministic PD-052 component rubric independently of Fit gates against fresh Employer-Origin detail evidence. It grants no ranking authority.

Current result:

- `67/71` jobs have fresh same-Origin Affinity calibration evidence;
- `45` match the persisted assessment revision exactly;
- `22` are fresh same-Origin revisions newer than the persisted assessment and are explicitly marked `unpersisted_current_revision`; they may be used for calibration/display evidence only, never authoritative ranking until normal persistence/requalification catches up;
- `4` current Product rows now return HTTP 404 and remain unavailable;
- the runtime weight vector exactly matches approved PD-052: `40% profile direction / 25% reliability / 20% data / 15% evidence quality`.

Highest current read-only legacy Affinity examples include:

- HDI `Data Scientist: Advanced Analytics & AI Engineer in Insurance` — `66.4`;
- Eraneos `Senior AI Engineer` — `65.3`;
- Eraneos `Senior Analytics Engineer` — `62.6` on a fresh unpersisted Origin revision;
- Eraneos `Data Engineer` — `62.3`;
- Finanz Informatik `AI Engineer / KI-Entwickler` — `62.3` on a fresh unpersisted Origin revision;
- 1KOMMA5 `Senior Analytics Engineer - Growth` — `60.4`.

These values are Affinity calibration only. For example the HDI Data Scientist has high Affinity but zero exact overlap across four currently observed skill labels; that does not prove negative Fit because Candidate-Fact tagging is not exhaustive. Conversely Hannover Re `Data Scientist` has lower Affinity (`45.5`) but all two currently observed skills are exactly backed; that still does not establish complete Fit while employment/hours/geography/seniority evidence remains unresolved.

## Runtime threshold contradiction

The active runtime policy reports `minimum_quality_score=60` under `product-v1-2026-09-03`, while approved `PD-051`, current Re-Entry and migration 078 retain **70/100**. Historical repository evidence shows the 60 cutoff was introduced during DEMO-001 hardening specifically to obtain five recommendations. That rationale conflicts with current `PD-050` (`at_most_no_fill`) and the F4B target where Top 5 is only a downstream projection.

No code in this branch changes the threshold. This contradiction is now an explicit operator decision rather than silent drift.

## Operator gate

The next action is no longer another diagnostic. Read `docs/planning/active/F4B-OPERATOR-GATE-001.md` and make the three bounded product-authority decisions there. Combined-score formula selection is deliberately **not** requested yet because there are still zero complete numeric Fit rows.

## Paid-provider budget ledger

Campaign cap for additional paid API/provider tokens: **USD 10.00**. Paid calls through this checkpoint: **0**. Incremental paid spend: **USD 0.00**. Remaining paid-provider budget: **USD 10.00**. Local DB reads, Employer-Origin read-only retrieval, repository work and GitHub CI did not debit the paid-provider ledger.