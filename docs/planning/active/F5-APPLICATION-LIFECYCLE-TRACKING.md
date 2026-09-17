# F5 — Application Lifecycle + Outcome Tracking

Status: ACTIVE — real signal-enhanced Gmail re-preview accepted; persistence qualification next

Canonical issue: `#737 / APP-TRACK-001`

## Outcome

Extend the Product journey beyond `draft_for_review` without inventing submission or communication truth:

`application prepared -> operator confirms submitted -> communication evidence observed -> event candidate -> reviewed/authoritative lifecycle state -> next action`

The operator must be able to answer which applications are active, when/how they were submitted, whether a reply exists, what kind of response is evidenced, what needs attention next, and whether a displayed state is authoritative or inferred evidence.

## Authority boundaries

1. **Submission authority is explicit.** A submitted application may exist only after explicit operator confirmation or another separately approved authoritative submission record.
2. **Communication evidence is not lifecycle authority.** Gmail/runtime evidence may create bounded event candidates; it may not silently mutate authoritative application state.
3. **Public/private split remains strict.** Public Pipeline owns schemas, contracts, read models, provider-free classifier/tests/UI semantics. Gmail credentials and raw private message handling stay private-runtime/secrets-bound.
4. **No automatic send or submit.** F5 introduces no email reply/send authority and no automatic application submission.
5. **Append-only provenance.** Authoritative lifecycle/history changes must be append-only or explicitly superseding.
6. **Deterministic first.** Exact identity/thread/domain/rule evidence is used before any future model assistance.

## Slice A — COMPLETE

PR `#911` established the real read-only Product reconciliation and proved there was no historical submitted-application/event authority to migrate.

## Slice B — COMPLETE

Migration `112_create_authoritative_application_lifecycle.sql` established:

1. `applications` — prepared/discovered application identity, never submission authority by presence alone;
2. `application_submissions` — sole submission authority;
3. `application_lifecycle_events` — append-only authoritative post-submit events;
4. `application_event_candidates` — communication evidence only.

`gold_product_v1_application_tracking` derives the authoritative surface only from prepared identity + explicit submission + active authoritative events:

`prepared -> applied -> reply -> interview -> offer -> closed`

Migration-112 terminal proof remained clean: no seeded application/submission/lifecycle/candidate truth.

## Mailbox-first correction — COMPLETE

Migration `113_enable_mailbox_first_application_tracking.sql` corrected the mandatory `silver_job_id` modeling gap without rewriting migration 112. Mailbox-first discovery can now exist without manufacturing a current JAP job or submission authority.

Terminal evidence:

- exact migration-113 apply `35186715621`: SUCCESS;
- independent post-apply + Product proof `35186749692`: SUCCESS;
- checksum drift `0`, pending migrations `0`;
- Product DB after apply had `0` applications, `0` mailbox-discovered, `0` observed-status, `0` attention, `0` unmatched.

## Real Gmail preview foundation — COMPLETE

Private runtime OAuth/read boundary remains deliberately narrow:

- Google Desktop OAuth + PKCE;
- exact scope `https://www.googleapis.com/auth/gmail.readonly`;
- per-message Gmail fetches use `format=metadata`, never `full`/`raw`;
- normalized private JSONL carries bounded Subject/Snippet, deterministic identity hints and SHA-256 mailbox/thread/message references;
- credentials/tokens remain local;
- no Gmail writes, JAP/PostgreSQL writes, application submissions or provider cost.

Observation hardening before the latest outcome work already added inbound/outbound direction, bounded counterparty domain, conservative employer/title recovery and hard aggregator-noise suppression.

## Historical real annual batch preflight — BEFORE LATEST OUTCOME HARDENING

The prior 2026 batch produced:

- `203` input observations;
- `93` rows inside the selected 2026 window;
- `93` valid, `0` invalid;
- `8` discoverable rows;
- `10` review-worthy rows;
- `83` `other`;
- `2` `ambiguous`;
- `8` unique application keys;
- `0` duplicate evidence rows;
- public-preflight Gmail network requests `0`;
- DB connections/writes `0`;
- application submission actions `0`.

PR `#924` merged the read-only batch preflight contract and qualified it before any apply/persistence mode exists.

## Outcome-evidence hardening — COMPLETE / MERGED

Real Gmail inspection exposed two distinct gaps:

### HDI 2026-07-23 — acknowledgement + rejection

The mail is a clear rejection but includes `Thank you for your application`. The previous classifier treated simultaneous deterministic classes as `ambiguous` even when only one was a high-impact outcome.

Public PR `#925` changes deterministic precedence generically:

- exactly one high-impact class (`rejection`, `offer_signal`, `interview_invitation`, `assessment_request`, `withdrawal_confirmation`) outranks background acknowledgement/recruiter language;
- multiple conflicting high-impact classes still return `ambiguous` and require review;
- acknowledgement plus generic recruiter wording resolves as acknowledgement rather than a false lifecycle conflict.

### Capgemini 2026-06-21 — decisive rejection after Gmail snippet boundary

The real Gmail message is a rejection, but the metadata snippet ends before the decisive rejection wording. Expanding per-message fetches to `full`/`raw` was rejected because it would broaden private-content exposure unnecessarily.

Runtime PR `#381` adds Gmail server-side `messages.list` searches for **strong lifecycle-specific phrases only**. Returned provider message IDs are immediately hashed and intersected with normalized observations. The runtime persists only bounded labels under `gmail_search_signals`; it does not persist search text, provider IDs, recipient addresses or message bodies.

Broad terms such as bare `Absage` or bare `Vorstellungsgespräch` are deliberately not sufficient high-impact signal evidence.

Public PR `#925` validates those labels fail-closed and feeds them into the same deterministic classifier used by batch preflight and production ingestion. Allowed labels are exactly:

`rejection`, `offer_signal`, `interview_invitation`, `assessment_request`, `withdrawal_confirmation`.

The discovery threshold was not relaxed and all classifier results remain `evidence_only`.

Public PR `#927` fixed the direct operator CLI import path. Public PR `#928` then moved PostgreSQL-specific imports behind the actual persistence function and added a direct `python -S` subprocess regression, proving the public read-only preflight does not require site-packages/`psycopg`. Exact PR-928 candidate `49f8466fa47e8cb6c1d7e07707e473394d3345e5` passed F5 qualification `35250071633`, Re-entry `35250071679` and Pipeline CI `35250072571` before merge as public `main@1a2de9e9feefc35d42cb16c82ab5cddde5c78331`.

## Real signal-enhanced annual re-preview — ACCEPTED

The fresh private normalized JSONL has SHA-256:

`33265bb4da98ce422ff8df9318b8279651cc5231d45f3a6e948628ed2ccdc4b5`

The public preflight ran from exact public `main@1a2de9e9feefc35d42cb16c82ab5cddde5c78331` with `python3 -S`, proving the intended dependency-free read-only operator surface.

Measured 2026 result:

- `203` input observations;
- `93` rows inside the selected 2026 window;
- `93` valid, `0` invalid;
- `11` discoverable rows;
- `11` review-worthy rows;
- `82` `other`;
- `0` `ambiguous`;
- `9` unique application keys;
- `0` duplicate evidence rows;
- class counts: `8` `application_acknowledgement`, `3` `rejection`;
- `GMAIL_NETWORK_REQUESTS=0`;
- `DATABASE_CONNECTIONS=0`;
- `DATABASE_WRITES=0`;
- `APPLICATION_SUBMISSION_ACTIONS=0`.

Real regression findings are now correct:

1. HDI 2026-07-23 is `rejection`; HDI 2026-07-01 is `application_acknowledgement` under the same application identity.
2. Capgemini 2026-06-21 is `rejection`; Capgemini 2026-03-14 is `application_acknowledgement` under the same application identity.
3. Former ambiguity is eliminated (`2 -> 0`).
4. MODULAT 2026-01-12 is additionally discovered as a deterministic rejection.
5. Eleven discoverable messages produce nine unique application identities, which is expected lifecycle evidence multiplicity rather than duplicate processing.

The re-preview gate is therefore passed. No Gmail rescan is required for persistence design; the exact JSONL/hash above is the accepted private batch evidence for the next qualification slice.

## Persistence qualification — ACTIVE / FIRST WRITE STILL BLOCKED

The remaining blocker is no longer classification quality. It is source-message idempotency and safe reclassification.

Current schema problem:

- `application_event_candidates` uniqueness is `(source_kind, evidence_fingerprint, candidate_class)`;
- current `evidence_fingerprint` contains `mailbox_account_fingerprint`, `message_reference`, `candidate_class` and `reason_code`;
- therefore the same immutable Gmail message can receive a different fingerprint after classifier/evidence improvement and leave two co-active candidate interpretations.

The next persistence contract must distinguish **message identity** from **interpretation identity**:

1. Stable source identity for Gmail is derived from `source_kind + mailbox_account_fingerprint + source_message_reference`.
2. Reprocessing the same source message with the same interpretation is a no-op.
3. Reclassification of the same source message creates/preserves audit history while making exactly one interpretation active; the prior interpretation is explicitly superseded/dismissed.
4. Distinct messages for the same application remain distinct evidence rows and can represent lifecycle progression. HDI and Capgemini are the real acceptance fixtures for this rule.
5. Supersession applies to communication evidence only. It may not create `application_submissions` or `application_lifecycle_events`.
6. A batch apply path must be bounded, preflightable, idempotent and require explicit exact-main apply authority.
7. No Gmail write scope is added.

## Sole next action

Implement and exact-head qualify the smallest **source-message identity + candidate supersession persistence package**:

1. add a new immutable migration after 113 rather than rewriting prior migrations;
2. add provider-free schema/ingest tests for same-message no-op, same-message reclassification supersession, and different-message same-application lifecycle progression;
3. add a read-only batch persistence preflight that predicts application inserts, candidate inserts, candidate no-ops and candidate supersessions without DB writes;
4. run Full Suite/Ruff/React/F5 qualification and merge exact tested head;
5. stop before migration apply / real Gmail batch persistence and request the real DB migration-preflight/operator authority gate.

Until that package is qualified: **no DB persistence of the Gmail batch, no Gmail write scope, no automatic application submit, no model-created authority and no authoritative lifecycle transition from mailbox evidence**.

## Next slices after persistence qualification

### Control Center lifecycle UX — queued

Primary operator surface remains:

`Prepared -> Applied -> Reply -> Interview -> Offer -> Closed`

Attention/next-action is primary. Evidence, uncertainty and provenance use progressive disclosure. Broader post-freeze UX simplification remains isolated in `#910`.

### Bounded transition automation — queued

Only after measured precision and explicit operator policy approval. False authoritative transition count must remain zero during shadow/canary.

## Sequencing

Current frozen campaign order remains:

`F5 -> F6`

F4C is operator accepted and complete. F6 remains blocked until F5 reaches its package-completion authority.
