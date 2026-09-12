# JAP Current Re-Entry

Status: canonical current re-entry projection + frozen product campaign sequencing authority

Read this file from canonical `refs/heads/main` before continuing product work. During an active package, the exact package branch may carry a fresher candidate version of this authority; merge only after exact-head qualification.

## Live repository checkpoint — 2026-09-12

Canonical base before F3 is `main@fb06e1191ae044d0c0547e9136c7860b097bdf5b`, merged through PR #862.

Published/installed product truth before F3:

- JAP Control Center Desktop **v1.0.23** is published from `fb06e1191ae044d0c0547e9136c7860b097bdf5b`;
- automatic post-release local deploy run `34688050141` completed PASS;
- installed operator acceptance PASS: VALUNY jobs are visible in `All jobs`, `Open original` reaches the real VALUNY Origin posting, and Sources reports VALUNY `ACTIVE · LAST RUN 2 JOBS`;
- therefore `CR-F2-001` is CLOSED and F3 entry is authorized.

Active F3 work:

- branch: `agent/f3-truth-lifecycle-hardening`;
- Draft PR: **#864 — F3: harden Bronze→Silver→Gold truth and lifecycle**;
- target desktop release: **1.0.24**;
- migration `109_create_canonical_vacancy_identity_truth.sql` is already applied on the Product DB, tracked and immutable;
- active package authority: `docs/planning/active/f3_truth_lifecycle_hardening.md`.

No F4 work begins before F3 exact-head qualification, merge, automatic v1.0.24 release/deploy and installed operator acceptance.

## Product authority that does not change during the campaign

Employer-Origin admission has one authority path:

`company candidate -> generic evidence-driven origin layers -> strict source proof -> valid source -> vocabulary/search -> query-proven vacancies -> structure learning -> Origin Bronze -> parser family -> Silver -> lifecycle/identity truth -> Gold -> Product -> Control Center`

Rules:

1. Current generic `proof=PASS` is the sole Employer-Origin source-validity authority.
2. Source admission and job admission are separate; a valid source may legitimately deliver zero current jobs.
3. Market sensors are discovery/freshness evidence only and never normal Product review authority.
4. Only credible real vacancies with exact Origin evidence enter Bronze.
5. Learned vocabulary improves understanding but never creates source-validity authority.
6. Product/Control Center consumes upstream truth; UI-only repair is not product authority.
7. No employer-specific production exception, fuzzy title/company merge or weak URL rewrite may establish vacancy identity.

## Frozen campaign execution policy

Normal package flow:

`implementation -> focused tests -> Full Suite/Ruff/React/Windows contracts -> real Product/Origin proof -> merge exact tested head -> immutable Windows release -> automatic local deploy -> interactive operator test -> record evidence -> next package`

Exact-head discipline:

- a branch change invalidates earlier final qualification authority;
- migrations already tracked in the Product DB are immutable; corrections use a new migration;
- package PRs remain Draft until the final exact head has the required qualification and real Product proof;
- release/deploy automation is part of the product contract, not an operator workaround.

## Cascading residual rule

A bounded, understood, non-critical residual may cross a package boundary only when it retains a stable ID, concrete evidence, explicit risk/open condition and named next checkpoint. Security/credential, destructive/data-loss, irreversible migration and external side-effect boundary problems do not cascade silently.

Every package checkpoint re-lists inherited residuals. A residual never ages out by omission: close it with regression evidence, explicitly reclassify it, or move it through a separately authorized future decision.

## Active residual ledger

### `CR-F0-001` — FI Origin alias identity duplication — CLOSED technically in F3

Origin: F0.

Historical symptom: the same Finanz Informatik vacancy appeared through parallel employer-Origin aliases with and without a leading `/de/` path segment.

F3 closure does **not** globally strip `/de/` and contains no FI-specific production rule. Migration 109 creates provider-neutral `gold_vacancy_identity` and retains every Bronze/Silver member while selecting one Gold representative through this hierarchy:

1. same Origin host + strong labelled/schema vacancy identifier;
2. exact page-declared canonical Origin URL;
3. tightly bounded same-run structured-detail equivalence for generic Origin aliases;
4. exact observed Origin URL;
5. isolated Silver identity.

Real persisted proof run `34711951430` on exact head `3bbdba2bf7f0ca8e729a772132030ce13be77eeb` PASS:

- `58` FI identity members retained;
- `5` actual duplicate groups collapsed;
- `2` strong-ID groups: `E362/B` and `420/B`;
- `3` bounded same-run detail-equivalence groups;
- exactly one representative per group;
- `19` FI rows visible in current Product review with no remaining known locale-alias duplicate.

The durable final F3 acceptance additionally requires presentation-layer duplicate repair to be exactly zero. `CR-F0-001` therefore remains CLOSED subject only to the normal final F3 exact-head regression/operator checkpoint; it is not carried as an open residual.

### `CR-F1-001` — fresh company -> F1 discovery -> CAND-001 persistence -> proof/activation — OPEN / carried

Origin: F1.

The downstream persisted-source path is independently proven, but a fresh company identity has not yet completed the full F1 discovery -> CAND-001 persistence -> proof -> activation path in one real Product E2E.

Last explicit failing evidence remains run `34565632246`: 11 `f1_not_found`; Windhoff was selected but CAND-001 returned `manual_review_required`, so no candidate URL was written.

F3 does not naturally alter company discovery/persistence. Do not distort F3 to close this residual. It remains visible for the next natural discovery/persistence touchpoint and becomes a mandatory campaign-end decision if no such touchpoint occurs.

### `CR-F2-001` — positive delivery/Product closure — CLOSED

Origin: F2.

Closed through exact-head VALUNY Product acceptance, merge/release v1.0.23, automatic local deployment and installed operator acceptance. Do not carry it into F3/F4.

## F0 — Origin Learning + Review Truth Foundation — COMPLETE

Delivered through 1.0.19/1.0.20. Current review excludes stale/dead and sensor-only rows; Origin rows retain independent `Published` and `First JAP observed`; safe exact identity dedupe is supported. Former residual `CR-F0-001` is closed by F3 upstream canonical identity.

## F1 — Company -> Official Origin Jobspace Discovery — CAPABILITY SHIPPED / `CR-F1-001` CARRIED

Shipped in 1.0.21 plus later persistence/reliability bridge work. Discovery remains generic, evidence-driven and fail-soft. CAND-001 remains the sole candidate URL writer. The only inherited open F1 residual is the missing fresh-company real E2E described above.

## F2 — Dynamic-Origin + B-ITE Product Closure — COMPLETE

1.0.22 established Dynamic-Origin source admission. PR #862 / v1.0.23 closed positive B-ITE delivery through the canonical path without VALUNY-specific parsing or provider allowlisting.

Proven real chain:

`proof=PASS -> active -> recurring B-ITE ingestion -> current observations -> Bronze -> Silver -> Gold/Product -> Control Center All jobs -> real Origin navigation`

Installed operator acceptance is complete; `CR-F2-001` is closed.

## F3 — Bronze -> Silver -> Gold Truth/Lifecycle Hardening — ACTIVE, target 1.0.24

Purpose: make downstream vacancy truth resistant to stale, dead and duplicate vacancies regardless of upstream family.

Implemented F3 boundary:

- migration 109 adds `gold_vacancy_identity` without rewriting historical Bronze/Silver rows;
- `gold_current_job_opportunities` and `gold_product_v1_job_readiness` consume one canonical representative upstream;
- strong labelled/schema vacancy identity has highest authority;
- exact canonical/observed Origin URL remains safe exact evidence;
- bounded same-run detail equivalence exists only for generic Origin rows with exact structured-detail agreement, distinct observed URLs, compatible strong-ID evidence and the same locale-neutral path;
- no fuzzy title/company identity exists;
- lifecycle remains driven by `gold_job_lifecycle_health` and explicit/current authoritative observations;
- presentation may remain defensive but final acceptance requires it to suppress zero further duplicates.

Real pre-cleanup Product acceptance `34711951430` proved:

- migration history: 109 tracked, checksum-clean, zero pending;
- FI: `58` members -> `5` canonical duplicate groups -> `19` current visible jobs;
- lifecycle audit: `431` stale, `5` inactive, `16` source families;
- current-view lifecycle leakage: `0`;
- at least `1` real multi-location Silver job exists;
- Product review rows: `65` at that observation point;
- sensor/non-current Product review leakage: `0`;
- marker: `F3_CANONICAL_VACANCY_IDENTITY_ACCEPTANCE=PASS`.

The durable acceptance is `.github/workflows/f3-truth-lifecycle-acceptance.yml` plus `scripts/accept_f3_truth_lifecycle.py`. It runs on every push to the F3 branch so the final head, not an earlier implementation head, owns release authority.

F3 installed operator acceptance after v1.0.24:

- About reports v1.0.24 / expected source revision;
- current Employer-Origin vacancies remain visible;
- known FI alias pairs no longer duplicate in `All jobs`;
- stale/inactive rows are absent from current review while audit/history remains available;
- market-sensor-only rows remain outside normal review;
- multi-location stays one vacancy;
- previously accepted VALUNY F2 path still works.

Sole next action: **finish final exact-head F3 qualification on PR #864.** Require durable F3 truth/lifecycle acceptance, Pipeline CI including Full Suite/Ruff/React, Windows Control Center contract and re-entry identity PASS on the same final head. If green, mark #864 ready, merge exact qualified head, require automatic v1.0.24 release and post-release local deployment, then stop for installed operator acceptance. Do not enter F4 before that PASS.

## F4 — Decision Intelligence Coverage — targets 1.0.25 and 1.0.26

### F4A — Profile Fit coverage — 1.0.25

Every current review job gets evidence-backed Candidate<->Job Profile Fit or explicit `insufficient_evidence`; preliminary role affinity remains separate. Normalize requirements, approved Candidate Facts, geography/work model/commute, seniority, skills/capabilities and hard requirements with factor-level explanations and coverage metrics.

### F4B — Ranking coverage — 1.0.26

Only fit-complete, lifecycle-current and hard-gate-qualified jobs become rankable. Every exclusion exposes a reason. Deterministic ranking remains authority. Operator acceptance reconciles `current -> fit complete -> rankable -> Top 5`.

## F5 — Application Lifecycle + Gmail-backed Outcome Tracking — target 1.0.27

Persist application identity linked to canonical vacancy where possible; use append-only application events and Gmail evidence with provenance; never infer submission without evidence. Applications become a real Control Center portfolio and outcomes may become later evaluation evidence without rewriting deterministic ranking authority.

## F6 — Template-Authoritative Application Drafting — target 1.0.28

Approved template/layout is hash-bound authority. JAP mutates only explicit editable content zones using Candidate Facts and exact current Origin evidence. Render/layout validation must prove no unauthorized layout change. Human review remains mandatory; no automatic submit/send.
