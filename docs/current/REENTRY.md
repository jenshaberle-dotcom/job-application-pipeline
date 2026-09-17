# JAP Current Re-Entry

Status: canonical current re-entry projection + frozen product campaign sequencing authority

Read this file from canonical `refs/heads/main` before continuing Product work. During an active package, an exact package branch may carry a fresher candidate version; merge only after that package's required exact-head qualification.

## Live repository checkpoint — 2026-09-17

Canonical public repository state before this re-entry refresh:

`main@192fac0cda6b112f45f954f94fde9285d81f5f0d`

Canonical private runtime state:

`jenshaberle-dotcom/job-pipeline-runtime@2f39b449f9df3e97cb373435797677195d61f590`

Public PR `#925` and runtime PR `#381` completed the pre-persistence mailbox outcome hardening. The public exact tested head was `3ddc4ee2869a4b60bd85f84585ecb45179c4fa98`; terminal gates were F5 application lifecycle qualification `35221200869` SUCCESS, Pipeline re-entry target identity `35221200667` SUCCESS and Pipeline CI `35221201032` SUCCESS. The runtime exact tested head was `e18d526e1ba185b7e9f7a2e4cb28cf3920c8545c`; terminal gates were Runtime re-entry target identity `35221220970` SUCCESS and F5 Gmail read-only bridge PR check `35221221052` SUCCESS.

The last recorded installed/operator-accepted Product remains:

`1fa2f36a4881a481f44c4d4ae32f7e1b7479f99b` / `jap-winapp-desktop-v1.0.37`

F5 remains open. No no-op Windows release is required for these read-only/private-preview hardening slices.

## Frozen campaign sequence — current

`F5 -> F6`

Completed current-campaign packages are F0, F1 capability delivery, F2, F3, F4A, F4B and F4C. F5 Slices A and B plus the mailbox-first schema correction are complete. F5 is now at the **signal-hardened real Gmail re-preview gate before first persistence**.

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

## F5 — ACTIVE / SIGNAL-HARDENED REAL GMAIL RE-PREVIEW

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

### Real Gmail preview + observation hardening — COMPLETE THROUGH PRE-PERSISTENCE CONTRACT

The private runtime OAuth/read boundary is established and remains exact `gmail.readonly`. Gmail per-message reads remain `format=metadata`; normalized output contains bounded Subject/Snippet, deterministic identity hints and hashed mailbox/thread/message references. Gmail writes, JAP/PostgreSQL writes and provider cost remain zero in the preview bridge.

The latest real annual mailbox batch used for pre-hardening measurement produced:

- input rows `203`;
- 2026 window rows `93`, all `93` valid;
- discoverable rows `8`;
- review-worthy rows `10`;
- other rows `83`;
- ambiguous rows `2`;
- unique application keys `8`;
- duplicate evidence rows `0`;
- Gmail network requests from public preflight `0`;
- database connections/writes `0`;
- application submission actions `0`.

Those measurements exposed two real semantic gaps and one low-impact ambiguity pattern:

1. HDI 2026-07-23 is a clear rejection whose bounded text also contains acknowledgement wording. Public classification now lets one clear high-impact outcome outrank background acknowledgement/recruiter wording; conflicting high-impact outcomes still remain `ambiguous`.
2. Capgemini 2026-06-21 is a clear rejection in the real Gmail message, but Gmail's metadata snippet ended before the decisive rejection phrase. Runtime PR `#381` therefore adds server-side Gmail `messages.list` searches for **strong lifecycle-specific phrases only**, hashes returned provider message IDs, and emits only whitelisted bounded labels in `gmail_search_signals`. It still downloads no full/raw body.
3. A genuine acknowledgement that also mentions Talent Acquisition is no longer treated as a lifecycle conflict merely because generic recruiter wording co-occurs.

Public PR `#925` validates `gmail_search_signals` fail-closed and feeds them into the same deterministic classifier used by batch preflight and production ingestion. Allowed signal classes are restricted to `rejection`, `offer_signal`, `interview_invitation`, `assessment_request`, and `withdrawal_confirmation`. Classifier output remains `evidence_only`; `should_discover_application` thresholds were not relaxed.

No claim is made that the **new signal-enhanced real annual preview** has passed yet. The previous 93-row measurement predates this hardening.

### First persistence remains blocked

Do not persist the old preview batch merely because its contract preflight passed. Before first mailbox persistence authority:

1. run a new real Runtime read-only annual Gmail scan from runtime `main@2f39b449f9df3e97cb373435797677195d61f590` to a fresh local JSONL;
2. run public `run_product_v1_f5_mailbox_batch_preflight.py` from current public main against that fresh JSONL for the intended 2026 window;
3. inspect class counts, discoverable identities, ambiguity, duplicate evidence and the HDI/Capgemini regressions;
4. only if the new signal-enhanced batch is acceptable may a separately qualified bounded persistence/apply path be introduced.

Until then: **no DB persistence of the Gmail batch, no Gmail write scope, no automatic application submit, no model-created authority, and no authoritative lifecycle transition from unreviewed mailbox evidence**.

One persistence-design residual must also be handled before first write: an unchanged Gmail message that was previously classified differently must not leave contradictory active candidates merely because `candidate_class`/`reason_code` participate in its evidence fingerprint. First-persistence qualification must define idempotent supersession/review semantics for such reclassification.

## Sole next action

Run the **new real signal-enhanced read-only Gmail annual scan**, then rerun the **public read-only batch preflight** on that fresh JSONL. Stop before DB persistence and report the measured result.

## F6 — queued

Template-Authoritative Application Drafting remains the final frozen package. Approved template/layout stays hash-bound; only explicit editable content zones may be generated from Candidate Facts and exact current Origin evidence. Human review remains mandatory; no automatic submit/send.

## Cascading residual rule

Active carried residuals remain:

- `CR-F1-001`: fresh company -> F1 discovery -> CAND-001 persistence -> proof/activation;
- `#891 / F4B-FOLLOWUP-001`: generic skill extraction, capability auto-fit, numeric Fit and Combined calibration in the next freeze campaign;
- `#910`: post-freeze operator UX simplification + Data Layers truth audit.
