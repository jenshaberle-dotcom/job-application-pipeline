# JAP Current Re-Entry

Status: canonical current re-entry projection + frozen product campaign sequencing authority

Read this file from canonical `refs/heads/main` before continuing Product work. During an active package, the exact package branch may carry a fresher candidate version of this authority; merge only after the package's required qualification.

## Live repository checkpoint — 2026-09-14

Canonical `main` at the start of this checkpoint is:

`ef74adf58d610e8a346a555b79af5800e2fc6fc6`

This includes the F4A implementation/release work plus JAP local-deploy corrections through PRs `#870`–`#872`.

### F4A v1.0.25 release/deploy truth

F4A baseline is technically shipped, but **not operator accepted**.

Immutable installed product:

- desktop release: `jap-winapp-desktop-v1.0.25`;
- released Product source: `948864965e282f6de4f95d1808d6c40e654b7bd6`;
- automatic local deploy run: `34779970878`;
- physical runner used successfully: `job-pipeline-runtime-warm-01-linux`;
- `JAP_LOCAL_DEPLOY=AUTO_APPLY_PASS`;
- `JAP_LOCAL_DEPLOY_INSTALLED_RELEASE=PASS version=1.0.25`;
- installed `current.json` pins version `1.0.25` to exactly `948864965e282f6de4f95d1808d6c40e654b7bd6`;
- update result: `success`;
- no pending update remains;
- headless desktop rejection proof: PASS.

The newer deploy control plane may live on a later `main` commit while the installed Product remains bound to the immutable release source. That separation is accepted.

The existing JAP runner structure is **not a Product blocker**. Shared-pool/warm-runner efficiency and remaining RCC cutover/performance debt stay owned by RCC unless they prevent an actual JAP acceptance run. Do not reopen the runner as a JAP F4 blocker merely because setup is inefficient.

### Installed F4A operator verdict

Result: **CORRECTIVE HARDENING REQUIRED — do not start F4B yet.**

The installed v1.0.25 surface correctly separates Profile Fit from Product Score and preliminary Role Affinity, correctly renders missing fit evidence as `insufficient_evidence`, and does not require a ranking decision from missing evidence. However, the underlying real vacancy metadata for seniority, skills/capabilities and related hard requirements is not semantically useful/reliable enough across the current real source mix.

This is inside the original F4A contract, not unrelated scope: F4A requires normalized job requirements from current authoritative vacancy evidence. The current generic extractor is too shallow for that product requirement. F4A therefore remains open as **F4A-Q — Job Requirement Evidence Quality Hardening**, target desktop release `1.0.26`.

The current `rankable = 5` observation is not itself a defect target. It may be downstream of evidence coverage, but the corrective package optimizes truth and evidence quality, never a larger count. A correct result may legitimately remain five.

### Additional operator findings frozen into the campaign

The v1.0.25 review also exposed two already-important product gaps that must not disappear after F4A:

1. **Source health/operator observability:** current source projections expose historical last-run success but do not reliably answer whether a source is healthy now, overdue, degraded, unreachable or simply valid with zero current jobs. `Sources`, `Data Layers` and `Operations` overlap and need explicit non-overlapping operator contracts. This is frozen as **F4C — Source Health + Operator Surface Consolidation**, target `1.0.28`, after F4B and before F5.
2. **Application lifecycle:** live tracking from application confirmation/recruiter email evidence is already the planned F5 scope under `APP-TRACK-001` / issue `#737`. F5 remains frozen, now target `1.0.29`. The top-level information architecture must also remove the current `Application` / `Applications` ambiguity: preparation is an action/workspace; `Applications` is the authoritative portfolio/lifecycle surface.

## Product authority that does not change during the campaign

Employer-Origin admission has one authority path:

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

## Frozen campaign execution policy

Normal package flow remains:

`implementation -> focused tests -> Full Suite/Ruff/React/Windows contracts -> real Product/Origin proof -> merge exact tested head -> immutable Windows release -> automatic local deploy -> interactive operator test -> record evidence -> next package`

Exact-head discipline remains mandatory:

- a branch change invalidates earlier final qualification authority;
- migrations already tracked in the Product DB are immutable; corrections use a new migration;
- package PRs remain Draft until the final exact head has the required qualification and real Product proof;
- release/deploy automation is part of the Product contract, not an operator workaround;
- an installed operator rejection keeps the package open even when CI, release and deploy are green.

### Frozen package sequence after v1.0.25 operator review

`F4A-Q / 1.0.26 -> F4B / 1.0.27 -> F4C / 1.0.28 -> F5 / 1.0.29 -> F6 / 1.0.30`

This is an extension of the existing freeze, not a replacement campaign. Do not skip F4A-Q to chase ranking count, source dashboard polish or Gmail integration.

## Cascading residual rule

A bounded, understood, non-critical residual may cross a package boundary only when it retains a stable ID, concrete evidence, explicit risk/open condition and named next checkpoint. Security/credential, destructive/data-loss, irreversible migration and external side-effect boundary problems do not cascade silently.

Every package checkpoint re-lists inherited residuals. A residual never ages out by omission: close it with regression evidence, explicitly reclassify it, or move it through a separately authorized future decision.

## Active residual ledger

### `CR-F1-001` — fresh company -> F1 discovery -> CAND-001 persistence -> proof/activation — OPEN / carried

Origin: F1.

The downstream persisted-source path is independently proven, but a fresh company identity has not yet completed the full F1 discovery -> CAND-001 persistence -> proof -> activation path in one real Product E2E.

Last explicit failing evidence remains run `34565632246`: 11 `f1_not_found`; Windhoff was selected but CAND-001 returned `manual_review_required`, so no candidate URL was written.

Do not distort F4A-Q/F4B merely to close this residual. Close it only at a natural discovery/persistence touchpoint or make an explicit campaign-end decision.

### `CR-F0-001` — FI Origin alias identity duplication — CLOSED

Closed by F3 upstream canonical vacancy identity plus exact-head and installed operator evidence. Historical Bronze/Silver members remain auditable; no employer-specific or fuzzy identity authority was introduced.

### `CR-F2-001` — positive delivery/Product closure — CLOSED

Closed through exact-head VALUNY Product acceptance, merge/release v1.0.23, automatic local deployment and installed operator acceptance.

## Completed packages

### F0 — Origin Learning + Review Truth Foundation — COMPLETE

Current review excludes stale/dead and sensor-only rows; Origin rows retain independent `Published` and `First JAP observed`; safe exact identity dedupe is supported.

### F1 — Company -> Official Origin Jobspace Discovery — CAPABILITY SHIPPED / `CR-F1-001` CARRIED

Discovery remains generic, evidence-driven and fail-soft. CAND-001 remains the sole candidate URL writer.

### F2 — Dynamic-Origin + B-ITE Product Closure — COMPLETE

Positive real chain proven:

`proof=PASS -> active -> recurring B-ITE ingestion -> current observations -> Bronze -> Silver -> Gold/Product -> Control Center All jobs -> real Origin navigation`

### F3 — Bronze -> Silver -> Gold Truth/Lifecycle Hardening — COMPLETE / v1.0.24 OPERATOR ACCEPTED

Current Product review consumes canonical vacancy identity and explicit lifecycle truth. Known FI Origin aliases no longer appear as duplicate vacancies in the installed Product.

## Active package — F4A-Q / target 1.0.26

Purpose: finish the original F4A promise by making job-side requirement evidence semantically usable while retaining fail-closed Profile Fit authority.

Required corrective direction:

- inventory the current Product review cohort by source family and evidence shape;
- compare extracted job requirement facts with exact authoritative Origin evidence;
- prefer authoritative structured vacancy metadata where present;
- preserve section/context information instead of relying only on whole-document flattened regex matching;
- keep bounded deterministic phrase extraction as fallback;
- preserve exact provenance/evidence references for asserted metadata;
- make conflicts/context-poor evidence explicit `unknown`;
- allow reusable ATS/document-family understanding, never employer-specific production truth exceptions;
- keep Candidate Fact privacy and exact-current review binding intact;
- replay authoritative detail changes through the existing revision/invalidation path.

Acceptance is defined in `docs/planning/active/F4A-PROFILE-FIT-COVERAGE.md`.

**Sole next action:** perform the real-source evidence audit for the current review cohort, identify concrete false/weak metadata patterns by reusable source/evidence family, then implement the smallest generic/section-aware extraction correction. Do not start F4B until the corrected exact head is released, automatically deployed and installed-operator accepted.

## F4B — Ranking coverage — target 1.0.27

Only fit-complete, lifecycle-current and hard-gate-qualified jobs become rankable. Every exclusion exposes a reason. Deterministic ranking remains authority. Operator acceptance reconciles `current -> fit complete -> rankable -> Top 5`.

F4B must not use a target rankable count as acceptance. Correct exclusion reasons and complete reconciliation are the acceptance truth.

## F4C — Source Health + Operator Surface Consolidation — target 1.0.28

Purpose and acceptance are frozen in `docs/planning/active/F4C-SOURCE-HEALTH-OPERATOR-SURFACE.md`.

Operator ownership model:

- `Sources`: source/origin lifecycle, cadence, current health, overdue/degraded/blocker/attention truth;
- `Data Layers`: Bronze/Silver/Gold inventory, flow, freshness and conversion/coverage;
- `Operations`: only distinct runtime execution/scheduler/queue/incident truth. If that distinct truthful read model is unavailable, merge/hide the redundant surface rather than preserve a count dashboard.

Historical `success` is not current source health.

## F5 — Application Lifecycle + Gmail-backed Outcome Tracking — target 1.0.29

Canonical product item: `APP-TRACK-001` / issue `#737`.

Persist application identity linked to canonical vacancy where possible. Submission authority comes only from explicit operator confirmation or another separately approved authoritative record. Gmail is read-only communication evidence: confirmation/recruiter/interview/offer/rejection messages may create provenance-backed event candidates, but must not silently rewrite application state.

Initial lifecycle remains:

`Prepared -> Applied -> Reply -> Interview -> Offer -> Closed`

Control Center information architecture must converge to one top-level `Applications` portfolio/lifecycle surface. `Prepare application` remains an action/workspace reachable from the relevant job/application flow; it should not remain a competing ambiguous top-level `Application` destination.

No automatic email reply and no automatic application submission.

## F6 — Template-Authoritative Application Drafting — target 1.0.30

Approved template/layout is hash-bound authority. JAP mutates only explicit editable content zones using Candidate Facts and exact current Origin evidence. Render/layout validation must prove no unauthorized layout change. Human review remains mandatory; no automatic submit/send.
