# F5 — Application Lifecycle + Outcome Tracking

Status: ACTIVE — read-only reconciliation first

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

## Repository baseline before F5 mutation

At `main@1fa2f36a4881a481f44c4d4ae32f7e1b7479f99b`:

- migration `077_create_product_v1_monolith_foundation.sql` provides `application_source_documents` and `application_draft_requests`;
- `application_draft_requests.status` stops at preparation/review states: `blocked_missing_sources`, `blocked_job_not_eligible`, `ready_for_generation`, `drafted_for_review`, `approved_by_operator`, `rejected_by_operator`;
- no submitted timestamp/channel, employer-response event, interview, offer/rejection outcome or append-only post-submit status authority is defined by that table;
- the current `Applications` Control Center surface deliberately renders a future lifecycle and states `No submitted applications yet` rather than fabricating persisted applications;
- the public repository contains planning references to Gmail but no Gmail implementation.

These are repository observations only. Real Product DB truth must be reconciled before schema or authority changes.

## Frozen-package slices

### Slice A — read-only lifecycle reconciliation

Measure the real Product DB and current UI/schema without mutation:

- relation/column inventory for current application tables/read models;
- row counts and status counts for application source documents and draft requests;
- distinct job identities represented by draft requests;
- presence of any existing post-submit/submission/event/status relations;
- whether current Product/UI has a persisted application-portfolio source or only static future-state copy;
- exact zero-side-effect boundaries.

The output is diagnostic authority only. It must not create a lifecycle policy merely because a similarly named relation exists.

### Slice B — authoritative application lifecycle + provenance schema

Only after Slice A evidence:

- define authoritative application identity and append-only submission/status event model;
- bind exact Silver/job/employer identity and explicit operator-confirmed submission timestamp/channel;
- add read models that distinguish authoritative state from evidence candidates;
- provider-free transition/idempotency/ambiguity tests.

### Slice C — read-only Gmail evidence bridge

Private runtime only:

- bounded mailbox/thread search;
- normalized evidence candidate payloads with message/thread IDs, sender/domain, timestamps and bounded evidence excerpts/fingerprints;
- prove zero send/reply/archive/delete actions.

### Slice D — deterministic-first event classification

Initial classes:

`application_acknowledgement`, `recruiter_contact`, `interview_invitation`, `assessment_request`, `offer_signal`, `rejection`, `withdrawal_confirmation`, `other`, `ambiguous`.

Every result carries reason/evidence and application-match provenance. Model assistance, if later justified, is residual-only and cannot silently mutate lifecycle authority.

### Slice E — Control Center lifecycle UX

Primary operator surface stays simple:

`Prepared -> Applied -> Reply -> Interview -> Offer -> Closed`

Attention/next-action is primary. Evidence, uncertainty and provenance use progressive disclosure. This package must not absorb the broader post-freeze UX simplification work tracked in `#910`.

### Slice F — bounded transition automation

Only after measured precision and explicit operator policy approval. False authoritative transition count must remain zero during shadow/canary.

## Sole next action

Implement and run **Slice A only** as an exact-head, provider-free, network-free, read-only Product reconciliation against the real local PostgreSQL state. Record its cohort/schema findings before introducing a migration or lifecycle write path.

## Acceptance for Slice A

- exact source SHA is recorded;
- real DB transaction is read-only;
- application relation/column inventory is explicit;
- counts/statuses are measured rather than inferred;
- draft/review states are never relabelled as submitted;
- existence of a relation alone never makes it application-state authority;
- current UI/static future-state is distinguished from persisted truth;
- `db_writes=0`, `provider_calls=0`, `gmail_reads=0`, `email_actions=0`, `application_state_mutations=0`.

## Sequencing

Current frozen campaign order is now:

`F5 -> F6`

F4C is operator accepted and complete. Post-freeze UX/Data-Layers polish is tracked separately in `#910` and must not pull this campaign backward.
