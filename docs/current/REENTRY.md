# JAP Current Re-Entry

Status: canonical current re-entry projection + frozen product campaign sequencing authority

Read this file from canonical `refs/heads/main` before continuing Product work. During an active package, the exact package branch may carry a fresher candidate version of this authority; merge only after the package's required qualification.

## Live repository checkpoint — 2026-09-17

Canonical public repository state:

`main@dbe216a452ac53ca323920fb2929eb44fb9dd1aa`

This main includes the F5 authoritative lifecycle foundation, the mailbox-first correction through migration `113_enable_mailbox_first_application_tracking.sql`, and the PostgreSQL view-order recovery from PR `#919`.

The last recorded installed/operator-accepted Product remains:

`1fa2f36a4881a481f44c4d4ae32f7e1b7479f99b` / `jap-winapp-desktop-v1.0.37`

An intermediate immutable F5 release `jap-winapp-desktop-v1.0.38` was published from `27a5e78fb3041eee1b1f3964676f62d1db82a067` by release run `35137017336`. Local deploy run `35137225884` staged it correctly and stopped fail-closed at the required GUI-consent gate; no later installed/operator acceptance for v1.0.38 is recorded here. F5 remains open and newer corrective public-main work now exists, so v1.0.38 is not package-completion authority.

F4C remains complete. Post-freeze operator simplification/Data-Layers consistency work stays isolated in `#910` and must not displace F5/F6.

## Frozen campaign sequence — current

`F5 -> F6`

Historical target-version arithmetic is not sequencing authority. Each package uses the next appropriate immutable release only after exact-head acceptance of the package state to be installed.

Completed current-campaign packages are F0, F1 capability delivery, F2, F3, F4A, F4B and F4C. F5 Slices A and B plus the mailbox-first schema correction are complete; F5 as a package remains active at the real Gmail preview gate.

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

Exact-head discipline remains mandatory:

- every branch change invalidates earlier final qualification authority;
- tracked migrations are immutable; corrections use a new migration;
- package PRs remain Draft until final exact-head qualification and required real Product proof are complete;
- release/deploy automation is Product contract, not workaround;
- installed operator rejection keeps a product-changing package open even when CI/release/deploy are green;
- private mailbox evidence remains non-authoritative until a separately qualified public ingestion contract consumes it.

## F4B — OPERATOR ACCEPTED / COMPLETE

Canonical product target `#885` is closed for this freeze campaign.

Stable future residual `#891 / F4B-FOLLOWUP-001` owns generic skill-extraction hardening, capability auto-fit, numeric Fit and Combined-score calibration in the next freeze campaign. It must not pull the current campaign backward.

The accepted product concepts remain distinct:

- Affinity: `Will ich diesen Job?`
- Candidate<->Job Fit: `Passt dieser Job zu mir?`
- Combined decision score: deferred synthesis after stronger Fit evidence exists;
- Top 5: downstream `at_most_no_fill` projection only.

## F4C — OPERATOR ACCEPTED / COMPLETE

Canonical item `#898 / F4C Source Health + Operator Surface Consolidation` is closed.

Accepted truth dimensions remain separate:

`lifecycle eligibility != scheduler/run history != current reachability != evidence freshness != delivery/product yield`

The final F4C implementation stopped treating historical run success as current health without cadence/freshness authority, preserved successful zero-yield as valid run truth, separated live reachability from scan success, removed redundant Operations navigation and removed the competing source-health table from Data Layers.

Post-freeze operator simplification/Data-Layers truth audit is isolated in `#910` and is not a blocker for F5/F6.

## F5 — ACTIVE / SLICE C REAL READ-ONLY GMAIL PREVIEW

Canonical item: `APP-TRACK-001` / issue `#737` and `docs/planning/active/F5-APPLICATION-LIFECYCLE-TRACKING.md`.

F5 extends the Product journey beyond `draft_for_review` into evidence-first post-application tracking:

`application prepared -> operator confirms submitted -> communication evidence observed -> event candidate -> reviewed/authoritative lifecycle state -> next action`

Authority rules:

- submission authority comes only from explicit operator confirmation or another separately approved authoritative submission record;
- Gmail/runtime communication is evidence only and may not silently rewrite lifecycle state;
- Gmail credentials/raw private messages remain private-runtime/secrets-bound;
- the public Pipeline repo owns schemas/read models/provider-free contracts/tests/UI semantics;
- no automatic email reply/send and no automatic application submit;
- lifecycle/status history is append-only or explicitly superseding, never destructive rewrite;
- deterministic identity/thread/domain/rule evidence precedes any future model assistance.

### F5 Slice A — COMPLETE

Merged via PR `#911` as `main@80dd0d1017fb46cc9cea9f2f34bea78924febc2e` after exact candidate `b990b1f16e8ee5e49e5e435afa2aab9578e435e5` passed:

- F5 real read-only DB reconciliation `35125652183`;
- Pipeline CI `35125652472`;
- Re-entry target identity `35125652242`;
- evidence artifact `10459645819`, zip SHA256 `37b3a36bdf9ac5cc13e737b207fc83e4f4776bdf1446e61cedf7ad15080fd8d1`.

Measured Product DB truth before mutation had zero historical submitted-application/event authority.

### F5 Slice B — COMPLETE

Migration `112_create_authoritative_application_lifecycle.sql` established four deliberately separated layers:

1. `applications`: prepared application identity; presence is **not submission authority**.
2. `application_submissions`: **sole submission authority** with explicit submitted timestamp/channel and `operator_confirmation` or `approved_authoritative_record` provenance.
3. `application_lifecycle_events`: append-only authoritative post-submit events; corrections supersede prior events rather than rewriting history.
4. `application_event_candidates`: communication evidence only; Gmail/manual/runtime candidates cannot directly advance lifecycle state.

`gold_product_v1_application_tracking` derives only:

`prepared -> applied -> reply -> interview -> offer -> closed`

from prepared identity + explicit submission + active authoritative events. Candidate rows may create attention but are excluded from authoritative stage derivation.

Terminal evidence on canonical `main@367e18f901710980db59569f9c370e62a31fa8b6`:

- migration-112 exact apply `35131672947`: SUCCESS;
- independent read-only post-apply `35132353319`: SUCCESS;
- focused contracts `21 passed`, Ruff PASS;
- checksum drift `0`, pending migrations `0`;
- required relations/constraints PASS;
- zero seeded application/submission/lifecycle/candidate truth.

### F5 mailbox-first correction — COMPLETE

A real modeling gap was then found: mandatory `applications.silver_job_id` prevented mailbox-first discovery when a communication could not yet be matched to a current JAP job. Additive migration `113_enable_mailbox_first_application_tracking.sql` corrected that without rewriting migration 112.

After PR `#919`, canonical public `main` is `dbe216a452ac53ca323920fb2929eb44fb9dd1aa`.

Terminal evidence:

- migration-113 exact apply `35186715621`: SUCCESS;
- independent read-only post-apply + Product proof `35186749692`: SUCCESS;
- Product DB after apply: `0` applications, `0` mailbox-discovered, `0` observed-status, `0` attention, `0` unmatched;
- evidence artifact `10482821186`, SHA256 `88557ee40da2606d5f0d08655a4a8b1675fda7ddac2dcc65ad7b5649a80358b9`;
- no invented application/submission/lifecycle truth.

### F5 Slice C — ACTIVE / PRIVATE RUNTIME GMAIL PREVIEW

The private runtime bridge is merged in `jenshaberle-dotcom/job-pipeline-runtime` as:

`main@c79311f67a203e5cacf0aad285e455ed8be7bc03`

via runtime PR `#374`.

Exact runtime evidence before merge:

- F5 Gmail read-only bridge contract `35187483965`: SUCCESS (`6/6` tests);
- Runtime re-entry `35187483663`: SUCCESS;
- exact scope `https://www.googleapis.com/auth/gmail.readonly`;
- metadata-only Gmail message reads;
- hashed mailbox/thread/message references;
- `gmail_writes=0`, `database_writes=0`, `provider_cost=0`.

The private bridge writes only a local normalized JSONL preview. It has no JAP/PostgreSQL persistence path and creates no application authority.

### Sole next action

Human OAuth gate only:

1. Create/supply a local Google OAuth **Desktop app** client with Gmail API enabled; keep the client JSON outside both repositories.
2. Run the private runtime `doctor` command locally.
3. Grant exactly `gmail.readonly` once through the runtime `authorize` command.
4. Run one real metadata-only `scan` to local JSONL.
5. Inspect hit count, sender-domain/title coverage, Gmail thread fragmentation, likely duplicate application identities and deterministic employer/job matching quality.

Only after that real preview evidence is acceptable may F5 add a normalized public mailbox-ingestion/persistence path. Before then: **no DB persistence, no Gmail write scope, no fake application, no model-created authority**.

## F6 — queued

Template-Authoritative Application Drafting remains the final frozen package. Approved template/layout stays hash-bound; only explicit editable content zones may be generated from Candidate Facts and exact current Origin evidence. Human review remains mandatory; no automatic submit/send.

## Cascading residual rule

A bounded, understood, non-critical residual may cross a package boundary only with stable ID, concrete evidence, explicit risk/open condition and named next checkpoint. Security/credential, destructive/data-loss, irreversible migration and external side-effect boundary problems do not cascade silently.

Active carried residuals:

- `CR-F1-001`: fresh company -> F1 discovery -> CAND-001 persistence -> proof/activation remains open and must not distort F5 merely to close it;
- `#891 / F4B-FOLLOWUP-001`: generic skill extraction, capability auto-fit, numeric Fit and Combined calibration in the next freeze campaign;
- `#910`: post-freeze operator UX simplification + Data Layers truth audit.
