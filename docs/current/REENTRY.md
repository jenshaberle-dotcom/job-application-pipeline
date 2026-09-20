# JAP Current Re-Entry

Status: canonical current re-entry projection + frozen product campaign sequencing authority

Read this file from canonical `refs/heads/main` before continuing Product work. During an active package, an exact package branch may carry a fresher candidate version; merge only after that package's required exact-head qualification.

## Live repository checkpoint — 2026-09-18

Canonical public repository state before this re-entry refresh:

`main@560417bd83e452d880e2c0e327c16c590de4fd9e`

Canonical private runtime state:

`jenshaberle-dotcom/job-pipeline-runtime@805ff8a751c3a3630879d9765658ec5c17ceec22`

Public PR `#925` and runtime PR `#381` completed the pre-persistence mailbox outcome hardening. Public PR `#927` then fixed the real direct-CLI preflight import path, and public PR `#928` decoupled the read-only preflight from PostgreSQL-driver availability. PR `#928` exact candidate `49f8466fa47e8cb6c1d7e07707e473394d3345e5` passed F5 application lifecycle qualification `35250071633`, Pipeline re-entry target identity `35250071679` and Pipeline CI `35250072571`, all SUCCESS, before merge as `1a2de9e9feefc35d42cb16c82ab5cddde5c78331`.

The current operator-visible Product is `jap-winapp-desktop-v1.0.40` from exact source `d725b7de482721cb83176e1ea1e643210a02df51`. Operator review confirms the precise-warning/status-cluster presentation is materially improved. F5 remains open for one final read-only UX linkage slice: compact portfolio rows plus `silver_job_id -> effective_stage` application status inside All jobs.

## Frozen campaign sequence — current

`F5 -> F6`

Completed current-campaign packages are F0, F1 capability delivery, F2, F3, F4A, F4B and F4C. F5 schema, mailbox-first correction, real Gmail re-preview, source-message supersession, first bounded persistence write and independent post-write proof are complete. F5 is now at the **compact portfolio + All-jobs application linkage delivery gate**. The underlying Gmail persistence and lifecycle truth are already terminally proven.

## Product authority that remains invariant

Employer-Origin admission retains one authority path:

`company candidate -> generic evidence-driven origin layers -> strict source proof -> valid source -> query-proven vacancy -> Origin Bronze -> Silver -> lifecycle/identity truth -> Gold -> Product -> Control Center`

Rules:

1. Current generic `proof=PASS` is the sole Employer-Origin source-validity authority.
2. Source admission and job admission remain separate.
3. Market sensors are discovery/freshness evidence only.
4. Only credible vacancies with exact Origin evidence enter Bronze.
5. Learned observers may improve discovery/understanding but create no source/Fit/ranking/application authority without separate qualification.
6. Product/Control Center consumes upstream truth; UI-only repair is not authority.
7. No employer-specific identity/ranking exception, fuzzy merge, weak URL rewrite or invented missing requirement is allowed.
8. Missing evidence stays missing/unknown unless an approved deterministic or reviewed authority resolves it.

## Frozen package execution policy

Normal product-changing package flow remains:

`implementation -> focused tests -> Full Suite/Ruff/React/Windows contracts -> real Product/Origin proof -> merge exact tested head -> immutable Windows release -> automatic local deploy -> interactive operator test -> record evidence -> next package`

Read-only diagnostic/private-preview slices that do not change installed Product behavior may merge after exact-head qualification without manufacturing a no-op Windows release.

Exact-head discipline remains mandatory. Tracked migrations are immutable; every branch change invalidates earlier final qualification authority; Gmail/runtime evidence remains evidence rather than authoritative lifecycle state; no automatic email reply/send or application submit is introduced by F5.

## F4C — OPERATOR ACCEPTED / COMPLETE

Canonical item `#898 / F4C Source Health + Operator Surface Consolidation` is closed. Accepted truth dimensions remain separate:

`lifecycle eligibility != scheduler/run history != current reachability != evidence freshness != delivery/product yield`

Post-freeze operator simplification/Data-Layers truth audit remains isolated in `#910` and is not a blocker for F5/F6.

## F5 — ACTIVE / FIRST REAL PERSISTENCE TERMINAL PASS; WINDOWS DELIVERY NEXT

Canonical item: `APP-TRACK-001` / issue `#737` and `docs/planning/active/F5-APPLICATION-LIFECYCLE-TRACKING.md`.

F5 extends the Product journey beyond `draft_for_review` into evidence-first post-application tracking:

`application prepared -> operator confirms submitted -> communication evidence observed -> event candidate -> reviewed/authoritative lifecycle state -> next action`

Authority rules:

- submission authority comes only from explicit operator confirmation or another separately approved authoritative submission record;
- Gmail/runtime communication is evidence only and may not silently rewrite lifecycle state;
- Gmail credentials/raw private messages remain private-runtime/secrets-bound;
- public Pipeline owns schemas/read models/provider-free contracts/tests/UI semantics;
- no automatic email reply/send and no automatic application submit;
- lifecycle/status history is append-only or explicitly superseding, never destructive rewrite;
- deterministic identity/thread/domain/rule evidence precedes any future model assistance.

### Slice A — COMPLETE

PR `#911` established the read-only real Product reconciliation. It proved zero historical submitted-application/event authority before F5 mutation.

### Slice B — COMPLETE

Migration `112_create_authoritative_application_lifecycle.sql` established four deliberately separated layers:

1. `applications`: prepared/discovered application identity; presence is not submission authority.
2. `application_submissions`: sole submission authority.
3. `application_lifecycle_events`: append-only authoritative post-submit events.
4. `application_event_candidates`: communication evidence only and excluded from direct authoritative stage derivation.

`gold_product_v1_application_tracking` derives only `prepared -> applied -> reply -> interview -> offer -> closed` from prepared identity + explicit submission + active authoritative events.

### Mailbox-first correction — COMPLETE

Migration `113_enable_mailbox_first_application_tracking.sql` made mailbox-first discovery possible without inventing a JAP job or submission authority. Exact migration apply `35186715621` and independent post-apply/Product proof `35186749692` were SUCCESS with checksum drift `0`, pending migrations `0`, and zero seeded application/submission/lifecycle/candidate truth.

### Real Gmail preview + observation hardening — COMPLETE THROUGH ACCEPTED SIGNAL RE-PREVIEW

The private runtime OAuth/read boundary is established and remains exact `gmail.readonly`. Gmail per-message reads remain `format=metadata`; normalized output contains bounded Subject/Snippet, deterministic identity hints and hashed mailbox/thread/message references. Gmail writes, JAP/PostgreSQL writes and provider cost remain zero in the preview bridge.

The historical pre-hardening annual batch produced `203` input rows, `93` rows in the selected 2026 window, `8` discoverable rows, `10` review-worthy rows, `83` other, `2` ambiguous, `8` unique application keys and `0` duplicate evidence rows. That batch exposed the HDI acknowledgement+rejection conflict, the Capgemini snippet-boundary rejection and the low-impact acknowledgement+recruiter ambiguity pattern.

Public PR `#925` hardened deterministic precedence and validates bounded `gmail_search_signals`. Runtime PR `#381` adds server-side Gmail `messages.list` searches for strong lifecycle-specific phrases only, hashes provider message IDs, downloads no full/raw body and emits only whitelisted signal labels.

The **new signal-enhanced real annual preview is now accepted**. Operator run on 2026-09-17 used private JSONL SHA-256 `33265bb4da98ce422ff8df9318b8279651cc5231d45f3a6e948628ed2ccdc4b5` and public `main@1a2de9e9feefc35d42cb16c82ab5cddde5c78331`. Public preflight result:

- input rows `203`;
- 2026 window rows `93`;
- valid rows `93`, invalid rows `0`;
- discoverable rows `11`;
- review-worthy rows `11`;
- other rows `82`;
- ambiguous rows `0`;
- unique application keys `9`;
- duplicate evidence rows `0`;
- class counts: `8` application acknowledgements, `3` rejections;
- Gmail network requests from public preflight `0`;
- database connections/writes `0`;
- application submission actions `0`.

The critical regressions are resolved in real evidence:

- HDI 2026-07-23 is now `rejection` while HDI 2026-07-01 remains `application_acknowledgement` for the same application identity;
- Capgemini 2026-06-21 is now `rejection` while Capgemini 2026-03-14 remains `application_acknowledgement` for the same application identity;
- the former ambiguity count drops from `2` to `0`;
- MODULAT 2026-01-12 is additionally discovered as a deterministic rejection;
- `11` discoverable evidence rows collapse to `9` unique application keys, confirming that multiple lifecycle messages for one application must remain distinct evidence rows under one application identity.

### Candidate source identity + migration 114 — COMPLETE

PR `#930` implemented the source-message identity/supersession contract and a provider-free persistence planner. PR `#931` added the exact-main real DB preflight trigger. The stable Gmail source identity is now independent of classifier interpretation: `source_kind + mailbox_account_fingerprint + source_message_reference`. Reclassification preserves audit history while migration 114 enforces exactly one active interpretation per source message; different Gmail messages for the same application remain independent evidence.

The accepted private annual preview remains exactly:

- JSONL rows `203`;
- SHA-256 `33265bb4da98ce422ff8df9318b8279651cc5231d45f3a6e948628ed2ccdc4b5`.

The operator persistence planner on exact public `main@a5a98205e7a6eec253e0a78ea5ba8e16bc439170` is accepted:

- input rows `203`;
- 2026 window rows `93`;
- valid / invalid `93 / 0`;
- persistence candidate rows `11`;
- skipped first-seen `other` rows `82`;
- predicted application inserts `9`;
- predicted candidate inserts `11`;
- predicted no-ops `0`;
- predicted supersessions `0`;
- classes: `8` acknowledgement, `3` rejection;
- plan SHA-256 `741f00096e44d8ea020819697ae335ae0ee8a9839beace6386fd3e13957eb3c5`;
- Gmail requests, DB writes, submission actions and authoritative lifecycle mutations all `0`.

Migration `114_application_event_candidate_source_identity.sql` is now **applied and independently post-apply qualified** on that same exact source:

- exact-main preflight run `35274669336`: SUCCESS;
- first apply attempt `35308823088`: fail-closed before mutation because RCC runtime context was stale; apply step skipped;
- operator RCC refresh then proved repository identity, checkout, env, interpreter and PostgreSQL `SELECT 1` capability `PASS`;
- exact apply run `35311387470`: SUCCESS;
- independent read-only post-apply run `35311424361`: SUCCESS;
- post-apply artifact `10533103923`, digest `sha256:b78bd0b142e5a7929b08864b3aaa5437d0d01ecc9f872f163510144c42b74e2b`;
- migration 114 tracked successful, pending migrations `0`, checksum drift `0`, duplicate active source identities `0`;
- post-apply proof performed no DB writes, Gmail reads, email actions, submission actions or authoritative lifecycle mutations.

The accepted Gmail batch is now persisted under explicit operator authority and independently post-write qualified.

### Bounded first persistence apply — COMPLETE / TERMINAL PASS

PR `#932` added the atomic hash-bound apply path and live-DB preflight. PR `#933` fixed the Git-source-SHA validator after the first operator preflight failed closed before any DB connection. The accepted live read-only preflight on exact `main@19fb4b7e1a36830d895161e19922dfa398e49bfd` proved:

- input rows `203`, window `93`, valid `93`, invalid `0`;
- input SHA-256 `33265bb4da98ce422ff8df9318b8279651cc5231d45f3a6e948628ed2ccdc4b5`;
- plan SHA-256 `741f00096e44d8ea020819697ae335ae0ee8a9839beace6386fd3e13957eb3c5`;
- planned application inserts `9`;
- planned candidate inserts `11`;
- candidate no-ops / supersessions `0 / 0`;
- classes `8 application_acknowledgement`, `3 rejection`;
- DB connections `1`, DB writes `0`;
- Gmail/email/submission/authoritative-lifecycle actions `0`.

The operator then explicitly authorized exactly that batch. Atomic apply completed with:

- `F5_MAILBOX_PERSISTENCE_APPLY=PASS`;
- transaction `committed`;
- exact effects `9 applications + 11 candidates`;
- apply report SHA-256 `51599f3848ae4befd78712c4f34c0badabef075ed4f062082ad9a52845b25e8e`;
- no Gmail action, application submission action or authoritative lifecycle mutation.

PR `#934` added the independent read-only post-write qualifier. PR `#935` separated historical apply source from current proof source. The terminal operator proof on current `main@560417bd83e452d880e2c0e327c16c590de4fd9e` produced report SHA-256 `9cc4626b6296f6bd90bb7a23e4ef83a676e1492e7e6cc7d28ec4e29cfbd3e96f` and proved:

- verified application rows `9`;
- verified candidate rows `11`;
- verified Product tracking rows `9`;
- active Gmail candidates `11`;
- scoped/global submission rows `0 / 0`;
- scoped/global authoritative lifecycle rows `0 / 0`;
- `authoritative_stage=prepared` remains separate from mailbox-observed/effective state;
- post-write DB writes `0`, Gmail network requests `0`, email/submission/lifecycle mutations `0`.

Issue `#737` terminal evidence comment: `5731105594`.

### Control Center lifecycle UX — IMPLEMENTED ON MAIN / DELIVERY PENDING

The public Product runtime and React surface already implement mailbox-first tracking:

`Prepared -> Applied -> Reply -> Interview -> Offer -> Closed`

Current `main` exposes `observed_stage`, `effective_stage`, mailbox-discovered application counts, external/mailbox-only application identities, bounded evidence detail and the explicit observed-vs-authoritative distinction.

Published desktop v1.0.38 predates that mailbox-first projection. Therefore a new immutable v1 release is required; changing only live DB truth is insufficient because v1.0.38 does not contain the current tracking surface.

The installed v1.0.39 operator review proved the real mailbox cohort is visible, but exposed two completion defects: attention semantics were over-broad and the list lacked status clustering; several mailbox-only cards also lacked useful job identity. v1.0.40 is the corrective Product slice. It narrows attention to true review-required evidence, groups cards by effective lifecycle stage, surfaces bounded job identity metadata, and adds a read-only accepted-preview-vs-DB enrichment preflight before any metadata repair write.

### v1.0.39 operator acceptance — PARTIAL / FOLLOW-UP OPEN

The installed v1.0.39 About screen proved version `1.0.39` and source `27c0c27b...`. The Applications screen proved the real persisted cohort is visible. Operator feedback found:

- HDI/other correctly classified high-confidence evidence still received the same amber warning because storage `unreviewed` state was conflated with actual review need;
- applications need lifecycle-stage clustering;
- some mailbox-only cards lack job title/employer detail.

Issue #737 comment `5740140017` records the defect boundary. No new Gmail or lifecycle authority is implied.

### v1.0.40 operator review — ACCEPTED WITH FINAL UX FOLLOW-UP

The operator confirms the corrected warning semantics, status clustering and richer job metadata are substantially better. Final F5 UX feedback is tracked in issue #737 comment `5740425082`:

- Applications should default to a compact row containing current effective status + job identity and expand on demand;
- All jobs should show the linked F5 application status for Silver-backed applications;
- the `Beworben` filter must exclude `prepared/Erkannt` identities;
- linked job detail should navigate directly to Applications;
- all linkage remains read-only and reuses F5 `silver_job_id -> effective_stage`.

Target release is `v1.0.41`.

### v1.0.42 final operator-linkage architecture — ACTIVE / PR #941

The v1.0.41 operator check exposed two separate completion items: current All-jobs warning density regressed after the Application column was inserted, and the job/application navigation remained a loose UI handoff rather than one coherent application state.

PR #941 / v1.0.42 now keeps these boundaries explicit:

- required/unknown/insufficient evidence is neutral pending presentation; stale/ambiguous/unsure remains amber and failed/blocked/rejected remains red;
- safe mailbox->Silver reconciliation remains read-only; unresolved linkage remains `Ungeklärt` rather than being treated as a negative application fact;
- Jobs and Applications consume one centrally owned Product-truth snapshot distributed inside the React application;
- refresh is owned by one ProductTruth provider and concurrent refresh requests are deduplicated;
- F4C, review controls, application preparation support and evidence preview no longer maintain independent Product-truth read/update paths;
- Jobs -> Applications uses persistent application state (`selectedApplicationId`) rather than a one-shot browser event;
- Applications -> Jobs uses the same application/Silver identity, including exact projected linkage, and navigates back only when that Silver job is actually present in the current All-jobs snapshot;
- a linked historical/stale job outside the current review scope is shown as such and never redirects to an unrelated visible row;
- the manual tracking fallback refreshes the shared Product truth after its explicit write instead of reloading the page.

The current live reconciliation still has exactly one deterministic HDI -> Silver #2 match, and that job remains outside the current Employer-Origin All-jobs review scope. Therefore bidirectional navigation is implemented generically but correctly fails closed for that historical live case.

No DB link persistence, Gmail action, automatic submission, authoritative lifecycle mutation, or second application-status heuristic is introduced.

## Sole next action

Exact-head qualify PR #941, merge, release and install v1.0.42, then perform one interactive operator acceptance of the shared-snapshot behavior, warning density, Applications portfolio, and bidirectional Jobs <-> Applications navigation. No application/lifecycle mutation is part of this gate.

## F6 — queued

Template-Authoritative Application Drafting remains the final frozen package. Approved template/layout stays hash-bound; only explicit editable content zones may be generated from Candidate Facts and exact current Origin evidence. Human review remains mandatory; no automatic submit/send.

## Cascading residual rule

Active carried residuals remain:

- `CR-F1-001`: fresh company -> F1 discovery -> CAND-001 persistence -> proof/activation;
- `#891 / F4B-FOLLOWUP-001`: generic skill extraction, capability auto-fit, numeric Fit and Combined calibration in the next freeze campaign;
- `#910`: post-freeze operator UX simplification + Data Layers truth audit.
