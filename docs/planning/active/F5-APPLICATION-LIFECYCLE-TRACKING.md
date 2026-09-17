# F5 — Application Lifecycle + Outcome Tracking

Status: ACTIVE — Slice C real read-only Gmail evidence preview gate

Canonical issue: `#737 / APP-TRACK-001`

## Outcome

Extend the Product journey beyond `draft_for_review` without inventing submission or communication truth:

`application prepared -> operator confirms submitted -> communication evidence observed -> event candidate -> reviewed/authoritative lifecycle state -> next action`

The operator must be able to answer which applications are active, when/how they were submitted, whether a reply exists, what the evidenced response class is, what needs attention next, and whether a displayed state is authoritative or inferred evidence.

## Authority boundaries

1. **Submission authority is explicit.** A submitted application may exist only after an explicit operator confirmation or another separately approved authoritative submission record.
2. **Communication evidence is not lifecycle authority.** Gmail/runtime evidence may create bounded event candidates; it may not silently mutate authoritative application state.
3. **Public/private split remains strict.** The public Pipeline repo owns schemas, contracts, read models, provider-free classification rules/tests and UI semantics. Gmail credentials/raw message handling stay private-runtime/secrets-bound.
4. **No automatic send or submit.** F5 introduces no email reply/send authority and no automatic application submission.
5. **Append-only provenance.** Authoritative lifecycle/history changes must be append-only or explicitly superseding; no destructive rewrite of historical state.
6. **Deterministic first.** Exact identity/thread/domain/rule evidence is used before any model assistance. A future model may assist residual ambiguity but does not create authority.

## Slice A — COMPLETE

Merged by PR `#911` as `main@80dd0d1017fb46cc9cea9f2f34bea78924febc2e`.

Exact tested candidate: `b990b1f16e8ee5e49e5e435afa2aab9578e435e5`.

Terminal evidence:

- F5 reconciliation run `35125652183`: SUCCESS;
- Pipeline CI `35125652472`: SUCCESS;
- Re-entry target identity `35125652242`: SUCCESS;
- evidence artifact `10459645819`, zip SHA256 `37b3a36bdf9ac5cc13e737b207fc83e4f4776bdf1446e61cedf7ad15080fd8d1`.

Real Product DB truth before lifecycle mutation:

- application-shaped relations: `3`;
- `application_draft_requests`: `0` rows / `0` distinct jobs;
- submitted-like draft states: `0`;
- post-submit/submission/event/outcome candidate relations: `0`;
- DB writes/provider calls/Gmail reads/email actions/submission actions/application-state mutations: all `0`.

Conclusion: there was no historical submitted-application/event authority to migrate.

## Slice B — COMPLETE

Migration `112_create_authoritative_application_lifecycle.sql` established four distinct layers:

1. `applications` — prepared application identity. Presence means **Prepared**, never Applied.
2. `application_submissions` — the **only submission authority**, requiring timestamp/channel plus `operator_confirmation` or `approved_authoritative_record` provenance.
3. `application_lifecycle_events` — append-only authoritative post-submit events. Corrections add a superseding event rather than rewriting history.
4. `application_event_candidates` — communication evidence only. Candidate existence/review never directly advances authoritative lifecycle stage.

`gold_product_v1_application_tracking` derives the operator-facing authoritative stage only from prepared identity + explicit submission + active authoritative events:

`prepared -> applied -> reply -> interview -> offer -> closed`

Slice-B terminal evidence on canonical `main@367e18f901710980db59569f9c370e62a31fa8b6`:

- exact migration-112 apply run `35131672947`: SUCCESS;
- independent read-only post-apply run `35132353319`: SUCCESS;
- focused contracts `21 passed`, Ruff PASS;
- checksum drift `0`, pending migrations `0`;
- required relations/constraints PASS;
- no seeded application/submission/lifecycle/candidate truth.

## Mailbox-first correction — COMPLETE

F5 then exposed a real modeling gap: `applications.silver_job_id` was structurally mandatory, which prevented mailbox-first discovery for communication that cannot yet be matched to a current JAP job. The correction was additive migration `113_enable_mailbox_first_application_tracking.sql`; historical migration 112 remained byte-immutable.

Migration 113 now allows mailbox-first evidence without manufacturing application authority, extends the tracking projection with mailbox discovery/observed-status fields and preserves the migration-112 view column prefix required by PostgreSQL `CREATE OR REPLACE VIEW`.

Canonical public state: `main@dbe216a452ac53ca323920fb2929eb44fb9dd1aa`.

Terminal evidence:

- exact migration-113 apply run `35186715621`: SUCCESS;
- independent read-only post-apply + real Product proof `35186749692`: SUCCESS;
- Product DB after apply: `0` applications, `0` mailbox-discovered, `0` observed-status, `0` attention, `0` unmatched;
- evidence artifact `10482821186`, SHA256 `88557ee40da2606d5f0d08655a4a8b1675fda7ddac2dcc65ad7b5649a80358b9`;
- no invented application/submission/lifecycle truth.

## Slice C — ACTIVE: real read-only Gmail evidence preview

The private runtime bridge is merged in `jenshaberle-dotcom/job-pipeline-runtime` as `main@c79311f67a203e5cacf0aad285e455ed8be7bc03` via runtime PR `#374`.

The bridge boundary is deliberately narrow:

- OAuth Desktop Authorization Code + PKCE;
- exact scope `https://www.googleapis.com/auth/gmail.readonly`;
- Gmail message fetches use `format=metadata`, never raw/full bodies;
- normalized preview contains bounded Subject/Snippet, sender domain, deterministic hints and SHA-256 mailbox/thread/message references;
- credentials/tokens remain local and are never committed or uploaded;
- preview output is local JSONL only;
- Gmail writes `0`, JAP/PostgreSQL writes `0`, provider cost `0`.

Exact runtime evidence before merge:

- F5 Gmail boundary contract `35187483965`: SUCCESS (`6/6` tests);
- Runtime re-entry `35187483663`: SUCCESS;
- contract output: `gmail_writes=0 database_writes=0 provider_cost=0`.

### Slice C acceptance sequence

1. Operator creates/supplies a Google OAuth **Desktop app** client with Gmail API enabled and keeps the client JSON outside the repository.
2. Operator runs local `doctor`, then grants the exact `gmail.readonly` scope once via the runtime `authorize` command.
3. Run one real read-only `scan` to local JSONL.
4. Measure real hit count, sender-domain/title coverage, Gmail thread fragmentation, likely duplicate application identities and how often employer/job identity can be matched deterministically.
5. Only if that evidence is acceptable may normalized observations be bridged into the public JAP mailbox-ingestion contract.

No application row, event candidate row or authoritative lifecycle event may be created merely to make the preview look complete. Gmail evidence remains non-authoritative.

## Slice D — queued: deterministic-first event classification

Initial classes:

`application_acknowledgement`, `recruiter_contact`, `interview_invitation`, `assessment_request`, `offer_signal`, `rejection`, `withdrawal_confirmation`, `other`, `ambiguous`.

Every result carries reason/evidence and application-match provenance. Model assistance, if later justified, is residual-only and cannot silently mutate lifecycle authority.

## Slice E — queued: Control Center lifecycle UX

Primary operator surface stays simple:

`Prepared -> Applied -> Reply -> Interview -> Offer -> Closed`

Attention/next-action is primary. Evidence, uncertainty and provenance use progressive disclosure. This package must not absorb the broader post-freeze UX simplification work tracked in `#910`.

## Slice F — queued: bounded transition automation

Only after measured precision and explicit operator policy approval. False authoritative transition count must remain zero during shadow/canary.

## Sole next action

Reach the **human OAuth gate only**: create/supply the local Google Desktop OAuth client, grant exactly `gmail.readonly`, run one real metadata-only preview, and inspect the resulting matching/thread evidence.

Do **not** add a DB persistence path, Gmail write scope, model-based authority or fake application before that preview evidence exists.

## Sequencing

Current frozen campaign order remains:

`F5 -> F6`

F4C is operator accepted and complete. Post-freeze UX/Data-Layers polish is tracked separately in `#910` and must not pull this campaign backward.
