# JAP Current Re-Entry

Status: canonical current re-entry projection + frozen product campaign sequencing authority

Read this file from canonical `refs/heads/main` before continuing Product work. During an active package, an exact package branch may carry a fresher candidate version; merge only after that package's required exact-head qualification.

## Live repository checkpoint — 2026-09-17

Canonical public repository state before this re-entry refresh:

`main@1a2de9e9feefc35d42cb16c82ab5cddde5c78331`

Canonical private runtime state:

`jenshaberle-dotcom/job-pipeline-runtime@805ff8a751c3a3630879d9765658ec5c17ceec22`

Public PR `#925` and runtime PR `#381` completed the pre-persistence mailbox outcome hardening. Public PR `#927` then fixed the real direct-CLI preflight import path, and public PR `#928` decoupled the read-only preflight from PostgreSQL-driver availability. PR `#928` exact candidate `49f8466fa47e8cb6c1d7e07707e473394d3345e5` passed F5 application lifecycle qualification `35250071633`, Pipeline re-entry target identity `35250071679` and Pipeline CI `35250072571`, all SUCCESS, before merge as `1a2de9e9feefc35d42cb16c82ab5cddde5c78331`.

The last recorded installed/operator-accepted Product remains:

`1fa2f36a4881a481f44c4d4ae32f7e1b7479f99b` / `jap-winapp-desktop-v1.0.37`

F5 remains open. No no-op Windows release is required for these read-only/private-preview hardening slices.

## Frozen campaign sequence — current

`F5 -> F6`

Completed current-campaign packages are F0, F1 capability delivery, F2, F3, F4A, F4B and F4C. F5 Slices A and B plus the mailbox-first schema correction and signal-enhanced real Gmail re-preview are complete. F5 is now at the **persistence qualification / source-message supersession design gate before first mailbox write**.

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

## F5 — ACTIVE / REAL RE-PREVIEW ACCEPTED; PERSISTENCE QUALIFICATION

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

### First persistence remains blocked on source-message idempotency

The real re-preview gate is passed, but the current candidate table still cannot safely persist reclassification history. `application_event_candidates` uniqueness is based on `(source_kind, evidence_fingerprint, candidate_class)`, while `evidence_fingerprint` contains `message_reference`, `candidate_class` and `reason_code`. Therefore the same unchanged Gmail message can produce a second active candidate after classifier/evidence improvement.

Before first mailbox persistence, F5 must qualify a source-message identity contract with these properties:

1. Gmail source identity is stable on `source_kind + mailbox_account_fingerprint + source_message_reference`, not on classifier output.
2. Reprocessing an unchanged message with the same interpretation is a true no-op.
3. Reclassification of the same message preserves audit history but leaves exactly one active candidate interpretation; the prior interpretation is explicitly superseded/dismissed rather than co-active.
4. Multiple different Gmail messages for the same application remain independent evidence and may legitimately represent lifecycle progression, as the HDI and Capgemini real pairs prove.
5. Candidate supersession affects only evidence projection; it creates no submission row and no authoritative lifecycle event.
6. The bounded persistence path must have a dry-run/preflight mode and exact explicit apply authority; Gmail writes remain impossible.

Until that contract and its migration/apply path are separately qualified: **no DB persistence of the Gmail batch, no Gmail write scope, no automatic application submit, no model-created authority, and no authoritative lifecycle transition from mailbox evidence**.

## Sole next action

Implement and exact-head qualify the **F5 source-message idempotency + candidate supersession persistence contract**, including schema migration, provider-free tests and a bounded read-only batch persistence preflight. Stop before applying any new migration or writing the real Gmail batch; the next operator/authority gate is the real DB migration preflight for that exact merged main.

## F6 — queued

Template-Authoritative Application Drafting remains the final frozen package. Approved template/layout stays hash-bound; only explicit editable content zones may be generated from Candidate Facts and exact current Origin evidence. Human review remains mandatory; no automatic submit/send.

## Cascading residual rule

Active carried residuals remain:

- `CR-F1-001`: fresh company -> F1 discovery -> CAND-001 persistence -> proof/activation;
- `#891 / F4B-FOLLOWUP-001`: generic skill extraction, capability auto-fit, numeric Fit and Combined calibration in the next freeze campaign;
- `#910`: post-freeze operator UX simplification + Data Layers truth audit.
