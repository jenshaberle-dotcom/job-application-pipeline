# JAP Current Re-Entry

Status: canonical current re-entry projection + frozen product campaign sequencing authority

Read this file from canonical `refs/heads/main` before continuing Product work. During an active package, the exact package branch may carry a fresher candidate version of this authority; merge only after the package's required qualification.

## Live repository checkpoint — 2026-09-15

Canonical accepted Product checkpoint:

`main@35224c9b8351a3a260ba5d5e51236d61bb7ed8f5`

That main commit closed F4A and froze the F4B Fit + Affinity target. The immutable installed desktop release remains:

`jap-winapp-desktop-v1.0.32`

Release `1.0.32` is bound to Product source SHA `ec2e411ad5240f38e3cc38ee7f76dbac369a8388`. Local deploy run `34970391624`, attempt `2`, completed successfully and proved the installed released identity plus bounded headless startup/rejection behavior.

The first deploy attempt stopped fail-closed in a transient WSL/Git handoff after successful release staging. The single retry traversed the same guarded path successfully. No Product or installer patch was justified by that transient failure.

## F4A — OPERATOR ACCEPTED / COMPLETE

F4A Profile Fit + requirement-evidence hardening is accepted and no longer blocks the frozen campaign.

The final R8 closure proved the current real cohort through:

`Employer Origin -> Bronze evidence -> Silver requirement sidecar -> Product V1 -> Control Center`

Final guarded refresh/convergence evidence established:

- `70` current proposals accounted for;
- `41` Silver requirement sidecars needed refresh before Apply;
- post-Apply `would_change_count = 0`;
- all reachable Product rows projected without extractor gap;
- coverage gate passed;
- zero legacy ambiguity;
- zero Silver -> Product/Control-Center projection loss;
- zero acceptance violations.

Installed operator review on `1.0.32` accepted the slice on 2026-09-15. The operator judged the Product materially more coherent both visually and semantically. Remaining imperfections are intentionally not F4A blockers unless future evidence proves a confident false requirement assertion.

Two bounded residuals are explicitly carried rather than reopening F4A:

- Issue `#883`: About/version entry is no longer discoverable in the installed UI. This is non-blocking UX/discoverability debt and should be restored at a natural later UI checkpoint, not via a standalone release.
- Issue `#884`: one Hannover Re vacancy exposes an operator-visible Profile Fit conflict. This is useful F4B calibration evidence. It remains acceptable because the Product exposes the conflict instead of silently promoting it to positive ranking/application authority.

## Frozen campaign sequence — unchanged

The campaign continues in this order:

`F4B -> F4C -> F5 -> F6`

Do not re-open F4A for fit/ranking polish unless a new acceptance-critical false-truth defect is proven.

Historical package target version numbers are no longer authority because corrective releases advanced the desktop to `1.0.32`. Every future package uses the next available immutable release version after its exact-head acceptance; package order, not old version arithmetic, is the frozen sequencing authority.

## Product authority that does not change during the campaign

Employer-Origin admission keeps one authority path:

`company candidate -> generic evidence-driven origin layers -> strict source proof -> valid source -> vocabulary/search -> query-proven vacancies -> structure learning -> Origin Bronze -> parser family -> Silver -> lifecycle/identity truth -> Gold -> Product -> Control Center`

Rules:

1. Current generic `proof=PASS` is the sole Employer-Origin source-validity authority.
2. Source admission and job admission are separate; a valid source may legitimately deliver zero current jobs.
3. Market sensors are discovery/freshness evidence only and never normal Product review authority.
4. Only credible real vacancies with exact Origin evidence enter Bronze.
5. Learned vocabulary improves understanding but never creates source-validity authority.
6. Product/Control Center consumes upstream truth; UI-only repair is not Product authority.
7. No employer-specific production exception, fuzzy title/company merge or weak URL rewrite may establish vacancy identity.
8. Job-requirement understanding may use reusable source-family/document contracts and authoritative structured fields, but not employer-specific truth exceptions.

## Frozen package execution policy

Normal package flow remains:

`implementation -> focused tests -> Full Suite/Ruff/React/Windows contracts -> real Product/Origin proof -> merge exact tested head -> immutable Windows release -> automatic local deploy -> interactive operator test -> record evidence -> next package`

Exact-head discipline remains mandatory:

- a branch change invalidates earlier final qualification authority;
- migrations already tracked in the Product DB are immutable; corrections use a new migration;
- package PRs remain Draft until the final exact head has the required qualification and real Product proof;
- release/deploy automation is part of the Product contract, not an operator workaround;
- an installed operator rejection keeps the package open even when CI, release and deploy are green.

## F4B — ACTIVE PACKAGE / CODEX HANDOFF

Active branch:

`agent/f4b-fit-affinity-reconciliation`

Active Draft PR:

`#887 — F4B: reconcile Fit + Affinity before ranking mutation`

Implementation head before this re-entry refresh:

`e2c51cc7be3f7fe553a92da9671075871223f112`

Do not treat that SHA as finally qualified. This re-entry update itself advances the branch head, and every further branch change invalidates earlier exact-head qualification authority.

### F4B truth established so far

The first provider-free/read-only current-cohort reconciliation proved that Combined Score is not yet the primary blocker.

Real Product evidence on `36b391b4dd611dca7271e90c1c6f78d71adb73d2`, workflow run `34975583253`, passed and showed:

- `70` current Product jobs;
- `70/70` origin-validated and active;
- `0` hard-filter passed;
- `2` Fit failed;
- `68` Fit unknown;
- `0` current PD-052 Affinity-authoritative rows;
- `0` Combined-calibration-eligible rows;
- `70/70` jobs already have the canonical Silver requirement sidecar;
- Silver sidecar currently exposes useful bounded evidence for `49` jobs with skills, `21` with language values, `20` with numeric weekly hours, `2` with seniority values and `1` with a canonical employment value;
- exact current Candidate Capability review is missing for `70/70`;
- Candidate Geography/Work-Model preference evidence is missing for `70/70`.

This exposed the central F4B wiring defect: the Control Center already consumes the newer `silver_job_requirement_evidence`, while authoritative hard-filter evaluation still depends on older `job_product_assessments` evidence fields. Therefore UI and decision authority can disagree even when the Silver sidecar already contains stronger current job-source evidence.

Issue `#884` / Hannover Re is not an employer-specific parser defect. The Working-Student / 20h vacancy is a truthful negative hard-/fit-conflict and must remain excluded rather than being special-cased.

### Candidate fix now in PR #887

Migration `111_bridge_silver_requirement_evidence_into_hard_filter.sql` and its guarded Apply workflow are present on the active branch but **have not been applied to the Product DB**.

Intended authority contract of migration 111:

- Silver sidecar is job-source evidence only, never Candidate Fact or capability-fit authority;
- only conflict-free `observed_bounded_text` evidence may become authoritative hard-filter source evidence;
- `source_absent`, `origin_unavailable` and conflicted fields remain unknown/fail-closed;
- when a current Silver sidecar exists, stale legacy assessment evidence must not silently outrank it;
- Candidate Capability remains a separate authority gate;
- active manual hard-filter reviews are bound to the current Silver evidence hash;
- a later Silver evidence-hash change must automatically supersede the old review;
- PD-052 ranking policy, Top-5 state and application/submission authority remain untouched.

The prepared single-purpose workflow is:

`.github/workflows/f4b-hard-filter-silver-bridge-apply.yml`

It must not be triggered until the exact parent head is fully qualified.

### Current qualification state

For implementation head `e2c51cc7be3f7fe553a92da9671075871223f112`:

- Re-Entry run `34976464799`: **SUCCESS**;
- Pipeline CI run `34976465329`: **FAILURE**;
- React Control Center build: **SUCCESS**;
- migration/tooling/governance contract validation: **SUCCESS** and recognizes `111` migrations;
- hard Ruff correctness gate: **SUCCESS**;
- Full Suite: **3346 passed, 1 failed**.

The sole CI failure is:

`tests/test_f4b_hard_filter_silver_bridge.py::test_bridge_does_not_change_top5_or_ranking_policy`

The failure is currently a brittle test implementation, not evidence of a migration-contract violation. The test executes:

`source.casefold().split("CREATE OR REPLACE VIEW", 1)[1]`

and raises `IndexError` because that exact literal split is not present after case-folding / does not match the migration text. Do not weaken migration 111, ranking boundaries or authority semantics merely to make this test green.

### Sole next action for Codex

Fix **only the faulty F4B bridge test contract** so it verifies the intended no-ranking/no-Top5/no-application boundary without depending on that invalid literal split. Keep migration 111 and Product authority semantics unchanged unless the corrected test uncovers a real contract defect.

Then, on the new exact branch head:

1. run focused F4B bridge/reconciliation tests and Ruff;
2. require full Pipeline CI green;
3. require Re-Entry green;
4. require the provider-free/read-only real F4B reconciliation green;
5. only after all of those are green may a new single-purpose trigger commit apply migration 111 to the Product DB;
6. after Apply, require migration convergence and rerun the real F4B reconciliation before granting any further F4B authority.

Do **not** trigger migration 111 before that qualification. Do **not** mutate PD-052, Top-5, Candidate Facts, capability-fit authority, application state or submission/send state while fixing this CI blocker.

After migration 111 is safely applied and re-proven, continue F4B in this order:

`Silver -> hard-filter authority convergence -> current Candidate-Fact capability review -> geography/work-model preference authority -> read-only Fit/Affinity/Combined calibration -> operator decision whether a new Product Decision may supersede PD-052`

Top 5 remains a derived presentation projection only and must never be quota-filled.

The existing approved contracts remain hard boundaries:

- `PD-050`: Top 5 means at most five; no quota fill;
- `PD-051`: minimum overall quality remains `70/100` until separately changed;
- `PD-053`: hard-filter failures cannot enter authoritative ranking; unknown required hard-filter evidence remains review-required;
- `PD-054`: missing required evidence blocks authoritative ranking;
- `PD-055/056`: score components, reasons, uncertainty and missing information remain operator-visible.

## F4C — Source Health + Operator Surface Consolidation

F4C remains queued immediately after F4B. `Sources`, `Data Layers` and `Operations` must converge on distinct truthful operator contracts. Historical `success` is not current source health.

Purpose and acceptance remain in `docs/planning/active/F4C-SOURCE-HEALTH-OPERATOR-SURFACE.md`.

## F5 — Application Lifecycle + Gmail-backed Outcome Tracking

Canonical item remains `APP-TRACK-001` / issue `#737`.

Submission authority comes only from explicit operator confirmation or another separately approved authoritative record. Gmail is read-only communication evidence and may not silently rewrite application state. No automatic email reply and no automatic application submission.

## F6 — Template-Authoritative Application Drafting

Approved template/layout remains hash-bound authority. JAP may mutate only explicit editable content zones using Candidate Facts and exact current Origin evidence. Human review remains mandatory; no automatic submit/send.

## Cascading residual rule

A bounded, understood, non-critical residual may cross a package boundary only when it retains a stable ID, concrete evidence, explicit risk/open condition and named next checkpoint. Security/credential, destructive/data-loss, irreversible migration and external side-effect boundary problems do not cascade silently.

Active carried residuals:

- `CR-F1-001`: fresh company -> F1 discovery -> CAND-001 persistence -> proof/activation remains open and must not distort F4B merely to close it.
- `#883`: About/version discoverability, next natural UI checkpoint.
- `#884`: Hannover Re Fit conflict, explicit F4B reconciliation input.

Completed campaign packages remain F0, F1 capability delivery, F2, F3 and F4A.
