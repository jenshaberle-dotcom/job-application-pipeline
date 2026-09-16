# F5 — Application Lifecycle + Outcome Tracking

Status: ACTIVE — Slice B authoritative lifecycle foundation

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

Conclusion: there is no historical submitted-application/event authority to migrate. Slice B may introduce a clean additive foundation.

## Slice B — ACTIVE

Migration `112_create_authoritative_application_lifecycle.sql` defines four distinct layers:

1. `applications` — prepared application identity bound to exact Silver job identity snapshot. Presence means **Prepared**, never Applied.
2. `application_submissions` — the **only submission authority**, one explicit submission record per application, requiring timestamp/channel plus `operator_confirmation` or `approved_authoritative_record` provenance.
3. `application_lifecycle_events` — append-only authoritative post-submit events. Corrections add a new event using `supersedes_event_id`; history is not rewritten.
4. `application_event_candidates` — communication evidence only. Gmail/manual/runtime evidence may create candidates, but candidate existence/review never directly advances authoritative lifecycle stage.

`gold_product_v1_application_tracking` derives the operator-facing authoritative stage only from prepared identity + explicit submission + active authoritative events:

`prepared -> applied -> reply -> interview -> offer -> closed`

Evidence candidates may set `attention_status=evidence_review_required`, but do not affect `authoritative_stage`.

### Slice B acceptance

- historical migrations remain byte-immutable;
- migration 112 is the sole pending migration before apply;
- schema/constraints prove identity, submission authority, append-only lifecycle and evidence-candidate separation;
- stage derivation excludes candidate classification/review state;
- correction/supersession cannot delete prior lifecycle history;
- no Gmail/provider/send/automatic-submit path exists;
- focused tests + Ruff + full CI green on exact head;
- migration preflight proves 0 checksum drift and exact sole-pending target;
- apply uses exact migration 112 only;
- post-apply real DB proof verifies relations/view and zero seeded application/submission/event/candidate rows;
- only then may Slice C start.

## Slice C — queued: read-only Gmail evidence bridge

Private runtime only:

- bounded mailbox/thread search;
- normalized evidence candidate payloads with message/thread IDs, sender/domain, timestamps and bounded evidence excerpts/fingerprints;
- prove zero send/reply/archive/delete actions.

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

Qualify **Slice B** on an exact head, prove migration 112 is the sole pending migration with zero checksum drift, then apply exactly migration 112 and run a post-apply real Product DB contract proof before any Gmail read or lifecycle write path is introduced.

## Sequencing

Current frozen campaign order remains:

`F5 -> F6`

F4C is operator accepted and complete. Post-freeze UX/Data-Layers polish is tracked separately in `#910` and must not pull this campaign backward.
