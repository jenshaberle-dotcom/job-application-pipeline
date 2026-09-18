# F5 — Application Lifecycle + Outcome Tracking

Status: ACTIVE — migration 114 applied/post-apply qualified; bounded first persistence apply qualification next

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

## Persistence qualification — MIGRATION 114 COMPLETE / FIRST BATCH WRITE STILL BLOCKED

PR `#930` implemented stable source-message identity, candidate supersession semantics and the provider-free persistence planner. PR `#931` added the read-only exact-main migration-114 preflight trigger.

The accepted real annual JSONL remains SHA-256:

`33265bb4da98ce422ff8df9318b8279651cc5231d45f3a6e948628ed2ccdc4b5`

The accepted persistence planner result on exact public `main@a5a98205e7a6eec253e0a78ea5ba8e16bc439170` is:

- input `203`, window `93`, valid `93`, invalid `0`;
- persistence candidate rows `11`, skipped first-seen `other` `82`;
- predicted application inserts `9`;
- predicted candidate inserts `11`;
- predicted no-ops `0`;
- predicted supersessions `0`;
- unique source messages `11`;
- classes `8 application_acknowledgement`, `3 rejection`;
- plan SHA-256 `741f00096e44d8ea020819697ae335ae0ee8a9839beace6386fd3e13957eb3c5`;
- Gmail requests, DB connections/writes, submission actions and authoritative lifecycle mutations `0`.

Migration `114_application_event_candidate_source_identity.sql` terminal evidence:

- exact-main read-only preflight `35274669336`: SUCCESS;
- first apply attempt `35308823088`: fail-closed at stale RCC runtime-context; migration apply step skipped;
- operator RCC refresh: repository identity, checkout, env, interpreter, PostgreSQL capability and WSL projection all `PASS`;
- exact migration apply `35311387470`: SUCCESS;
- independent read-only post-apply `35311424361`: SUCCESS;
- post-apply artifact `10533103923`, digest `sha256:b78bd0b142e5a7929b08864b3aaa5437d0d01ecc9f872f163510144c42b74e2b`.

The post-apply qualifier requires migration 114 tracked successful, no pending migrations, no checksum drift, required source-identity/supersession columns/constraints/indexes present, duplicate active source identities `0`, and the Product tracking view to exclude superseded evidence. Post-apply boundaries remain fully read-only.

The real Gmail batch has **not** been persisted.

## Atomic bounded first persistence apply — ACTIVE

The next package must make the first write mechanically narrow rather than relying on operator intent alone:

1. exact checkout SHA must match approved source SHA;
2. normalized JSONL SHA must match the accepted private evidence SHA;
3. a fresh live-DB state-aware persistence plan must hash to the approved plan SHA;
4. current migration-114 schema must pass before mutation;
5. live state snapshot + apply run inside one serializable outer PostgreSQL transaction;
6. only planned persistence rows are passed to the ingest path;
7. actual application inserts / candidate inserts / no-ops / supersessions must exactly equal the approved plan before commit;
8. application-submission and authoritative-lifecycle row counts must remain unchanged;
9. no Gmail network/write path exists in the public apply surface;
10. execution requires an explicit apply flag plus the dedicated approval token `F5-GMAIL-BATCH-PERSISTENCE-V1`.

## Sole next action

Qualify and merge the atomic bounded persistence apply package. Then run a fresh exact-main/live-DB read-only plan check against the accepted JSONL and stop at the explicit operator authority gate before the real batch write.

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
