# F5 — Application Lifecycle + Outcome Tracking

Status: ACTIVE — signal-hardened real Gmail re-preview gate before first persistence

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

## Real annual batch preflight — MEASURED BEFORE LATEST OUTCOME HARDENING

The real 2026 batch used for the previous preflight produced:

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

Runtime PR `#381`, merged as runtime `main@2f39b449f9df3e97cb373435797677195d61f590`, instead adds Gmail server-side `messages.list` searches for **strong lifecycle-specific phrases only**. Returned provider message IDs are immediately hashed and intersected with normalized observations. The runtime persists only bounded labels under `gmail_search_signals`; it does not persist search text, provider IDs, recipient addresses or message bodies.

Broad terms such as bare `Absage` or bare `Vorstellungsgespräch` are deliberately not sufficient high-impact signal evidence.

Public PR `#925`, merged as public `main@192fac0cda6b112f45f954f94fde9285d81f5f0d`, validates those labels fail-closed and feeds them into the same deterministic classifier used by batch preflight and production ingestion. Allowed labels are exactly:

`rejection`, `offer_signal`, `interview_invitation`, `assessment_request`, `withdrawal_confirmation`.

The discovery threshold was not relaxed and all classifier results remain `evidence_only`.

### Exact-head qualification

Public candidate `3ddc4ee2869a4b60bd85f84585ecb45179c4fa98`:

- F5 application lifecycle qualification `35221200869`: SUCCESS;
- Pipeline re-entry target identity `35221200667`: SUCCESS;
- Pipeline CI `35221201032`: SUCCESS, including Full Suite, Ruff, migration/governance and React build.

Runtime candidate `e18d526e1ba185b7e9f7a2e4cb28cf3920c8545c`:

- Runtime re-entry target identity `35221220970`: SUCCESS;
- F5 Gmail read-only bridge PR check `35221221052`: SUCCESS.

## Important truth boundary after hardening

The previous `93`-row real batch measurement predates the new signal enrichment. It is **not** evidence that the new runtime/public pair has passed a real annual re-preview.

First persistence remains blocked. No existing normalized JSONL should be applied merely because its old read-only preflight was green.

Before first write, also resolve reclassification idempotency: if the same Gmail message was once classified as one candidate class and later reclassified after better evidence, the persistence design must supersede/review the older candidate rather than leave contradictory active evidence merely because candidate class/reason participate in its evidence fingerprint.

## Sole next action

1. From runtime `main@2f39b449f9df3e97cb373435797677195d61f590`, run a **new real read-only annual Gmail scan** to a fresh private JSONL.
2. From current public main, run `scripts/run_product_v1_f5_mailbox_batch_preflight.py` against that fresh JSONL for the intended 2026 window.
3. Inspect counts, unique identities, duplicates, ambiguity and especially the HDI/Capgemini classifications.
4. Stop before database persistence and record the measured result.

Only after that new real signal-enhanced preview is acceptable may F5 introduce a separately qualified bounded persistence/apply path.

Until then: **no DB persistence of the Gmail batch, no Gmail write scope, no automatic application submit, no model-created authority and no authoritative lifecycle transition from unreviewed mailbox evidence**.

## Next slices after the re-preview gate

### Persistence qualification — BLOCKED ON SOLE NEXT ACTION

Add the smallest bounded/idempotent apply path only after the new real preview passes. It must preserve communication-as-evidence semantics, prove no submission/lifecycle authority is manufactured, and define safe reclassification supersession.

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
