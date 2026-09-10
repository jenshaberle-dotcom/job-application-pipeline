# JAP Current Re-Entry

Status: canonical current re-entry projection + frozen product campaign sequencing authority

Read this file from canonical `refs/heads/main` before continuing product work. `docs/current/README.md` remains useful general operational context, but this file is the sequencing authority where older text conflicts with it.

## Product authority that does not change during the freeze

The Employer-Origin acquisition architecture is version-independent and has one product admission path:

`company candidate -> generic evidence-driven origin layers -> strict source proof -> valid source -> vocabulary learning -> query-proven real vacancies -> structure learning -> Origin Bronze -> parser family -> normalized Silver -> lifecycle/product gates -> Gold -> Product -> Control Center`

The **generic evidence-driven layer model remains the sole Employer-Origin source-validity truth**. A source is valid when current generic evaluation reaches `proof=PASS`. Historical V1..V6 labels, demo cohorts, fixed benchmark cohorts, provider-specific registry membership and legacy approval state are not alternative admission authorities.

Source admission and job admission remain separate:

1. `proof=PASS` admits/activates a source.
2. Vocabulary and structure learning may improve how that source is understood without changing proof authority.
3. A valid source may return zero jobs without losing validity.
4. Only credible real vacancy records with exact Origin evidence may enter Origin Bronze.
5. Market sensors may discover companies or provide discovery evidence, but sensor rows are not normal Product review jobs.

The recurring `*` remains a non-semantic execution trigger. Learned source vocabulary is search/relevance evidence, not source-validity authority.

## Proven persisted baseline

PR #847 established the real persisted generic product path. Its exact-main activation run `34445141597` emitted `GENERIC_PRODUCT_ACTIVATION_E2E=PASS` and proved the normal chain through PostgreSQL, Silver, Gold/Product readiness and Control Center reads.

That baseline included 24 current proof-pass generic Employer-Origin sources, 121 persisted generic Bronze rows, 26 normal Silver rows and 26 Gold/Product-readiness identities at the time of the proof. Silver `575`, `Director Data and Analytics`, Clarios, was the first concrete unchanged identity proven through the full persisted downstream read path.

Subsequent Windows releases closed the operator/UI integration gaps:

- 1.0.17: Windows runtime binds the pinned local OSS detail layer (`extruct`, `trafilatura`) correctly.
- 1.0.18: Product review UI consumes canonical Product truth without the old demo-only visibility guard; Source projection and review-navigation Origin links were hardened.
- Installed/operator-proven 1.0.18 source revision before the freeze implementation: `b233809d769b5a25e749ff4f1c43e9abda14495b`.
- 1.0.19: F0 Origin-learning/review-truth foundation merged as main `77402ce6565c22f4c8d21207e95cb184b6926fd0`; local deploy run `34471391370` PASS on the managed warm runner.

## 1.0.19 operator checkpoint

The interactive operator test on 2026-09-10 materially improved Product truth and is a **partial PASS, not F0 exit**.

Observed PASS:

- `All jobs` no longer showed stale/dead jobs in the normal review list.
- BA/StepStone/other market-sensor jobs no longer appeared as Product review jobs.
- `Published` and independent `First JAP observed` values were present in the GUI. Their layout is presentation polish and is explicitly not a freeze blocker.
- real Employer-Origin rows such as Finanz Informatik remained visible and geography-eligible.

Observed residual:

- the same Finanz Informatik `Business Analyst für das OBB Pro ...` vacancy appeared twice with the same visible title/employer/date. The F0 dedupe rule was still source-local, so the same exact canonical Origin URL could survive when projected once through a legacy/specific Employer-Origin source and once through `generic_origin:*`.

Operator guidance for this residual:

- do **not** add title/company fuzzy dedupe;
- do **not** add a 42% affinity cutoff; preliminary role affinity is not authoritative Profile Fit and low preliminary scores can still hide relevant titles;
- do **not** do UI/location presentation polish in this closure patch;
- fix only the safe generic invariant: an exact canonical Origin URL identifies one vacancy across Employer-Origin source projections, while structured identifiers remain source-local unless a stronger shared namespace is proven.

Location/source-semantic quality continues in F2/F3 through Origin understanding and downstream truth hardening; no cosmetic CC work is required to close F0.

## Current repository/branch state

Current canonical main before the F0 residual patch: `77402ce6565c22f4c8d21207e95cb184b6926fd0`.

Current implementation branch:

`agent/f0-operator-residuals`

This branch is intentionally a narrow F0 closure patch. Allowed mutations are:

- exact canonical Origin URL dedupe across Employer-Origin source projections;
- focused regression tests proving cross-source exact-URL collapse while different URLs remain separate;
- immutable Windows release bump to 1.0.20 and matching release contracts;
- re-entry evidence/renumbering only.

Explicitly forbidden in this branch:

- fuzzy title/company dedupe;
- affinity/Profile-Fit/ranking changes;
- FI-specific extraction heuristics;
- location or date-column UI polish;
- F1 discovery work.

Finanz Informatik remains a reference Origin case, not an architectural special-case authority. No further employer-specific hardening is allowed unless fresh evidence from multiple independent Origins justifies a reusable parser family or generic capability.

# JAP Product Freeze Campaign

The following package order is frozen. Do not start unrelated features, portal-specific one-offs, new model/provider work, UI cosmetics or speculative refactors while a package is open. A later package may be researched read-only while CI/release waits, but only one product package may mutate the product path at a time.

Every release follows the same completion contract:

`implementation -> focused tests -> Full Suite/Ruff/React/Windows contracts -> real Product/Origin proof where applicable -> merge exact tested head -> immutable Windows release -> automatic local deploy -> interactive operator test -> update this re-entry with evidence -> next package`

A package is **not complete at merge**. The operator test is part of Definition of Done.

Because immutable 1.0.19 exposed one operator-visible F0 residual, F0 receives closure release **1.0.20**. All later frozen release numbers move forward by one. Scope/order do not change.

## F0 — Origin Learning + Review Truth Foundation — releases 1.0.19 + 1.0.20 closure — ACTIVE

Purpose: close the observed regressions and establish the early-learning architecture before expanding source coverage.

Bundled scope:

- company-specific Vocabulary Learning before Origin job acquisition;
- Structure Learning before Bronze using the same fetched detail HTML;
- parser-family evidence and structured identifiers;
- Origin multi-location Bronze -> Silver normalization;
- current-only Employer-Origin review scope;
- sensor rows excluded from normal job review;
- stale/dead Product memory excluded from current review while remaining auditable;
- safe identity dedupe: source-local structured vacancy id plus exact canonical Origin URL across Employer-Origin projections;
- `Published` and independent `First JAP observed` in Control Center.

Explicit non-goals:

- no more FI-only heuristics unless they immediately generalize;
- no fuzzy title/company dedupe;
- no new ranking algorithm;
- no automatic application tracking yet;
- no UI presentation polish.

1.0.20 closure gate:

- focused exact-URL cross-source dedupe regression passes;
- complete PR gates including Full Suite, Ruff, frontend build, Windows host contracts and real Generic Employer-Origin Product Proof;
- merge only exact green head;
- publish/deploy immutable 1.0.20.

Operator test 1.0.20:

1. About shows 1.0.20 and exact release SHA.
2. `All jobs` still contains current Employer-Origin vacancies only: no BA/StepStone sensor jobs and no stale/dead jobs.
3. `Published` and `First JAP observed` remain available; layout is not assessed.
4. The previously duplicated Finanz Informatik `Business Analyst für das OBB Pro ...` exact Origin vacancy appears once.
5. Two genuinely different Origin URLs with the same company/title remain separate vacancies.
6. `Open original` remains the real Origin detail page.

Exit: operator PASS + re-entry evidence. Only then F1 starts.

## F1 — Company -> Official Origin Jobspace Discovery — target release 1.0.21

Purpose: maximize the upstream multiplier: given only a company identity, find the official domain, careers/job space and likely ATS/job surface generically.

Bundled scope:

- evaluate public/open datasets and local libraries/reference implementations for company -> official website and careers/ATS discovery;
- inspect reusable ATS fingerprints, common careers URL patterns, structured metadata and public unauthenticated ATS endpoints;
- build this as a native deterministic JAP capability, not a dependency on a hosted tool/service;
- existing libraries/data may be used as research/reference and may be adopted only when locally pinned, inspectable and replaceable; no opaque external runtime authority;
- candidate domain -> careers surface -> ATS/portal fingerprint -> generic source proof handoff;
- impossible-control and host-bound validation remain fail-closed.

Operator test 1.0.21:

Take several genuinely fresh company names from discovery evidence and show in Control Center/diagnostics that JAP can resolve company -> official Origin jobspace -> proof outcome without a company allowlist.

Exit metric: measured discovery funnel (`company -> official domain -> careers space -> proof`) with failures classified, not hidden.

## F2 — Origin Understanding + Parser-Family Scale-Out — target release 1.0.22

Purpose: turn proof-valid sources into productive sources without creating one connector per employer.

Bundled scope:

- run a real 10-20 company cohort through `proof -> vocabulary -> query-proven jobs -> structure learning -> Bronze -> parser family -> Silver`;
- persist/measure per-source learned vocabulary, search mechanism, parser family and field coverage;
- form a parser family only when repeated independent source evidence justifies it;
- keep generic JSON-LD/Microdata/DOM extraction as first choice;
- sources not understood well enough remain explicit Bronze/structure-learning evidence rather than receiving ad-hoc parser code;
- improve Origin semantic understanding including source vocabulary, structured metadata and multi-location facts before downstream normalization;
- add stage-funnel observability for coverage and failure reasons.

Operator test 1.0.22:

Inspect multiple independent Origin families in Sources/Data Layers and several real jobs in `All jobs`; verify learned vocabulary/structure produces correct titles, employers, URLs, published dates and locations across more than one employer.

Exit metric: funnel counts and parser-family coverage are recorded in re-entry; no success claim based only on one FI-like source.

## F3 — Bronze -> Silver -> Gold Truth/Lifecycle Hardening — target release 1.0.23

Purpose: make the downstream truth boundary resistant to stale, dead and duplicate vacancies regardless of which upstream Origin family produced them.

Bundled scope:

- current/dead/stale determination from exact Origin evidence, source publication/valid-through and recurring observations;
- sensor evidence may support discovery/freshness diagnostics but cannot become review authority;
- vacancy identity hierarchy: structured requisition/vacancy id -> exact canonical Origin URL -> only then bounded evidence-based equivalence; never title similarity alone;
- multi-location vacancy identity must not fork one vacancy into multiple jobs;
- regression cohort across multiple Origin families for currentness, dedupe and lifecycle;
- Product/CC projections consume these invariants instead of repairing bad truth in UI code.

Operator test 1.0.23:

A curated real cohort must demonstrate: current jobs remain, deliberately stale/dead jobs leave current review, sensor-only rows stay out, known duplicate aliases collapse safely, and historical rows remain auditable.

## F4 — Decision Intelligence Coverage — releases 1.0.24 and 1.0.25

This is one package with two mandatory release/operator checkpoints because ranking must not get ahead of fit truth.

### F4A — Profile Fit coverage — release 1.0.24

Purpose: every current review job gets either an evidence-backed Jens<->Job fit result or an explicit `insufficient_evidence`, never a manufactured score.

Scope:

- requirements/capability evidence from normalized Origin detail data;
- compare against approved Candidate Facts;
- location/work model/commute, seniority, skills/capabilities and hard requirements remain distinguishable factors;
- preliminary role affinity stays visibly separate from authoritative Profile Fit;
- coverage funnel: current -> fit complete / insufficient evidence / blocked.

Operator test: sample high, medium and low-fit current Origin jobs and inspect factor-level explanations against the actual job detail and Candidate Facts.

### F4B — Ranking coverage — release 1.0.25

Purpose: rank the whole eligible current cohort, not just the old small subset.

Scope:

- only fit-complete, lifecycle-current, hard-gate-qualified jobs may become rankable;
- every excluded current job exposes the exact reason;
- deterministic ranking components remain authority; no ML/LLM ranking authority in this freeze;
- Top 5 is derived only from the complete eligible ranked cohort.

Operator test: `current -> fit complete -> rankable -> Top 5` counts reconcile, sorting does not alter ranking authority, and several ranked jobs have understandable factor breakdowns.

## F5 — Application Lifecycle + Gmail-backed Outcome Tracking — release 1.0.26

Purpose: close the product loop from discovered job to real application outcome.

Real seed evidence already exists in Gmail from 2026-09-10 for three applications:

- Finanz Informatik — `E362/B - AI Engineer / KI-Entwickler (m/w/d)`;
- enercity — `Data Engineer (m/w/d)`;
- ROSSMANN — `(Junior) Data Engineer (m/w/d) Logistics Business Analysis` (including identity-confirmation flow and later receipt confirmation).

These mails are evidence only until this package implements the persisted application model.

Bundled scope:

- persisted application identity linked to the canonical vacancy where possible;
- append-only application events: prepared/applied/receipt confirmed/interview/rejected/offer/withdrawn/follow-up;
- Gmail ingestion/classification for application lifecycle evidence with explicit provenance and no inferred submission when evidence is absent;
- `Applications` Control Center becomes a real portfolio rather than a placeholder;
- outcomes become future evaluation/learning evidence but do not directly rewrite deterministic ranking authority.

Operator test 1.0.26:

The three real 2026-09-10 applications appear correctly in CC with employer, role, applied/confirmation timestamps and current lifecycle state, with no duplicate ROSSMANN application caused by its two emails.

## F6 — Template-Authoritative Application Drafting — release 1.0.27

Purpose: reproduce the quality of the current chat-assisted application workflow while freezing user-approved layout/design.

Bundled scope:

- user supplies an approved template/layout version;
- template bytes/layout/style become hash-bound authority;
- JAP generates only bounded content deltas in defined editable zones;
- Candidate Facts remain authority for factual candidate claims;
- job-specific wording derives from exact current Origin job evidence;
- render/layout validation proves the template was not unintentionally redesigned;
- human review remains mandatory; no automatic submit/send.

Operator test 1.0.27:

Generate at least one real application package from an approved template, compare it with the source template and job posting, and verify only authorized content zones changed while visual/layout identity remained stable.

# Cross-cutting freeze invariants

These apply to every package and do not wait for a later release:

- Maintain a single funnel: `companies discovered -> official Origin found -> proof PASS -> vocabulary proven -> real jobs found -> structure understood -> Bronze -> Silver -> current -> fit complete -> rankable -> applied -> outcome`.
- Every stage exposes counts plus classified failure/unknown reasons.
- Market sensors are discovery inputs, not Product review authority.
- Origin detail evidence outranks listing/search-card heuristics for vacancy facts.
- No source-specific parser is added for one employer merely to improve counts. Reusable parser families require repeated evidence or a clearly generic standard/ATS contract.
- No fuzzy dedupe may suppress real vacancies without inspectable evidence.
- No LLM/ML layer becomes production decision authority during this deterministic freeze; later ML remains subordinate to deterministic truth and Candidate Facts.
- No new external hosted tool/service becomes a required runtime dependency for source discovery or parsing. Research may inspect external/open implementations; production capability must remain local, bounded and replaceable.
- Existing operator feedback (`Interesting`, `Not relevant`, `Unsure`) remains learning evidence and does not directly rewrite ranking.
- Re-entry must be updated at every release/operator checkpoint with exact SHA, run IDs, measured funnel delta and next package.

## Freeze completion / feature thaw

The feature freeze ends only after F6 operator PASS, or by an explicit user decision to amend this frozen campaign in this file. Bugs/security/runtime blockers may interrupt the sequence only to restore the active package; they do not silently reprioritize the campaign.

## Sole next action

**Finish the narrow F0 closure / release 1.0.20 from `agent/f0-operator-residuals`.**

Immediate sequence:

1. Keep the patch limited to exact canonical Origin URL dedupe across Employer-Origin source projections plus focused regression coverage and release metadata.
2. Open the F0 closure PR against exact current main `77402ce6565c22f4c8d21207e95cb184b6926fd0`.
3. Run normal Pipeline CI, Re-Entry Identity, Windows Control Center contract and real Generic Employer-Origin Product Proof.
4. Fix only evidence-backed failures; no UI polish, affinity/ranking work or FI-specific heuristics.
5. Merge only the exact fully-green head.
6. Publish immutable 1.0.20 and let the normal local-deploy path install it.
7. Re-run the narrow operator checklist above, especially the previously duplicated FI vacancy.
8. Record exact evidence here; then and only then begin F1.
