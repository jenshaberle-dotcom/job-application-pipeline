# JAP Current Re-Entry

Status: canonical current re-entry projection + frozen product campaign sequencing authority

Read this file from canonical `refs/heads/main` before continuing Product work. During an active package, the exact package branch may carry a fresher candidate version of this authority; merge only after the package's required qualification.

## Live repository checkpoint — 2026-09-16

Canonical installed/accepted Product source before the active F5 package:

`main@1fa2f36a4881a481f44c4d4ae32f7e1b7479f99b`

Immutable desktop release:

`jap-winapp-desktop-v1.0.37`

Release workflow `35123098242` published the Windows desktop host from that exact source. Post-release local deploy run `35123289806` then proved:

- exact release source handoff `1fa2f36a4881a481f44c4d4ae32f7e1b7479f99b`;
- `JAP_LOCAL_DEPLOY_INSTALLED_RELEASE=PASS`;
- installed desktop version `1.0.37`;
- matching pinned source SHA;
- `pending-update.json` absent after successful apply;
- bounded headless desktop rejection proof passed.

Interactive installed operator acceptance on 2026-09-16 confirmed:

- About reports `v1.0.37` and source `1fa2f36a4881…`;
- Sources separates latest scan/run truth, delivery/yield, job age and live reachability; live reachability remains explicitly `Not checked` when not measured;
- redundant Operations top-level navigation is absent;
- Data Layers presents the current-cohort Bronze -> Silver -> Gold path without the competing per-source health table.

Issue `#898` is closed as completed. F4C is operator accepted.

Operator feedback that does **not** reopen F4C is tracked by `#910`: reduce primary operator detail through progressive disclosure/status clusters/traffic-light semantics and re-audit Data Layers metric/cohort/time-window consistency against DB truth. `#910` is post-freeze work and must not displace F5/F6.

## Frozen campaign sequence — current

`F5 -> F6`

Historical target-version arithmetic is not sequencing authority. Each package uses the next available immutable release after exact-head acceptance.

Completed current-campaign packages are F0, F1 capability delivery, F2, F3, F4A, F4B and F4C.

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

Normal package flow remains:

`implementation -> focused tests -> Full Suite/Ruff/React/Windows contracts -> real Product/Origin proof -> merge exact tested head -> immutable Windows release -> automatic local deploy -> interactive operator test -> record evidence -> next package`

Exact-head discipline remains mandatory:

- every branch change invalidates earlier final qualification authority;
- tracked migrations are immutable; corrections use a new migration;
- package PRs remain Draft until final exact-head qualification and real Product proof are complete;
- release/deploy automation is Product contract, not workaround;
- installed operator rejection keeps a package open even when CI/release/deploy are green.

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

## F5 — ACTIVE / READ-ONLY RECONCILIATION FIRST

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

### Repository baseline before mutation

At accepted `main@1fa2f36…`:

- `application_source_documents` and `application_draft_requests` exist from migration 077;
- draft-request status stops at preparation/review (`blocked_*`, `ready_for_generation`, `drafted_for_review`, `approved_by_operator`, `rejected_by_operator`);
- the public contract has no approved submitted timestamp/channel, response event, interview, offer/rejection outcome or append-only post-submit lifecycle authority;
- the Control Center `Applications` surface deliberately says `No submitted applications yet` and renders future-state lifecycle copy rather than inventing persistence;
- public JAP contains Gmail planning boundaries but no Gmail implementation.

These are repository observations, not real DB conclusions.

### Sole next action

Run one **exact-head, provider-free, network-free, read-only real Product DB reconciliation** before introducing any lifecycle migration or write path. It must measure:

- current application-shaped relations, columns and relevant constraints;
- application source-document counts/statuses;
- draft-request counts/statuses and distinct job identities;
- presence of any existing post-submit/submission/event/outcome relations;
- current persisted Product/UI application-portfolio authority versus static future-state copy;
- explicit zero-side-effect boundary.

The baseline must prove:

`db_writes=0`, `provider_calls=0`, `gmail_reads=0`, `email_actions=0`, `application_submission_actions=0`, `application_state_mutations=0`.

Only after that evidence may F5 Slice B define the authoritative application/submission/status provenance schema.

## F6 — queued

Template-Authoritative Application Drafting remains the final frozen package. Approved template/layout stays hash-bound; only explicit editable content zones may be generated from Candidate Facts and exact current Origin evidence. Human review remains mandatory; no automatic submit/send.

## Cascading residual rule

A bounded, understood, non-critical residual may cross a package boundary only with stable ID, concrete evidence, explicit risk/open condition and named next checkpoint. Security/credential, destructive/data-loss, irreversible migration and external side-effect boundary problems do not cascade silently.

Active carried residuals:

- `CR-F1-001`: fresh company -> F1 discovery -> CAND-001 persistence -> proof/activation remains open and must not distort F5 merely to close it;
- `#891 / F4B-FOLLOWUP-001`: generic skill extraction, capability auto-fit, numeric Fit and Combined calibration in the next freeze campaign;
- `#910`: post-freeze operator UX simplification + Data Layers truth audit.
