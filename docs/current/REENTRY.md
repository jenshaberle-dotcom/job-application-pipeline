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

## Proven baseline and current release truth

PR #847 established the real persisted generic product path. Exact-main activation run `34445141597` emitted `GENERIC_PRODUCT_ACTIVATION_E2E=PASS` and proved PostgreSQL -> Silver -> Gold/Product readiness -> Control Center.

Relevant Windows/Product checkpoints:

- 1.0.17: pinned local OSS detail runtime (`extruct`, `trafilatura`) fixed.
- 1.0.18: canonical Product truth and Origin navigation aligned.
- 1.0.19: F0 Origin-learning/review-truth foundation merged as `77402ce6565c22f4c8d21207e95cb184b6926fd0`; local deploy run `34471391370` PASS.
- 1.0.20: exact Origin URL cross-source review dedupe merged as current main `b1360671658627f09d49b94f5bcadff7e5747674`; immutable release published; local deploy run `34475650818` PASS.

## F0 operator result — accepted with one carried residual

The 1.0.19/1.0.20 operator tests materially improved Product truth.

Observed PASS:

- normal `All jobs` no longer showed stale/dead jobs;
- BA/StepStone/other market-sensor rows no longer appeared as Product review jobs;
- `Published` and independent `First JAP observed` are both present; their layout is presentation polish and not a freeze blocker;
- Employer-Origin rows remain visible and geography-eligible;
- exact same canonical Origin URLs can collapse across different Employer-Origin source projections.

Carried residual `CR-F0-001`:

- Finanz Informatik `Data Platform Engineer (m/w/d)` still appears twice because the same real vacancy is exposed through two origin URL aliases:
  - `https://www.f-i.de/karriere/offene-stellen/frankfurt/data-platform-engineer-m-w-d`
  - `https://www.f-i.de/de/karriere/offene-stellen/frankfurt/data-platform-engineer-m-w-d`
- these are not exact canonical URL matches under the current conservative URL canonicalizer;
- do **not** solve this by globally stripping `/de/`, by title/company fuzzy matching, or by an FI-specific special case;
- preferred generic evidence hierarchy for this residual: explicit structured/labelled vacancy identifier and/or canonical/final Origin identity before URL fallback;
- the current generic detail extractor already understands schema.org `JobPosting.identifier`; F1 may extend generic explicit identifier/canonical-link evidence when justified.

Also explicitly deferred from F0:

- no hard cutoff at 42% preliminary affinity; low preliminary affinity can still contain relevant titles;
- no UI/date/location cosmetics;
- no Profile Fit or ranking changes.

# Frozen campaign execution policy

The package order remains frozen, but the release policy is now optimized for development throughput rather than one release per minor residual.

Normal package flow:

`implementation -> focused tests -> Full Suite/Ruff/React/Windows contracts -> real Product/Origin proof where applicable -> merge exact tested head -> immutable Windows release -> automatic local deploy -> interactive operator test -> record evidence -> next package`

## Cascading residual rule

A package may advance after its main product objective is operator-proven even when a **bounded, understood, non-critical residual** remains. Such a residual is carried into the next semantically suitable package instead of forcing an immediate standalone release.

A residual may cascade only when all are true:

- it is explicitly recorded here with a stable ID, concrete evidence and intended target package;
- it does not represent a security/credential issue, destructive/data-loss risk, irreversible migration problem or external side-effect boundary violation;
- the failure mode is visible and bounded rather than silently corrupting broad Product truth;
- carrying it forward creates useful overlap with the next package and avoids release-only churn;
- the next package adds a regression proof for it before claiming closure.

Residuals must not silently hop across multiple packages. If a carried residual is still open at the next package checkpoint, it must either be closed there or explicitly reclassified by operator decision.

This rule intentionally trades perfect package purity for faster end-to-end product progress.

## F0 — Origin Learning + Review Truth Foundation — COMPLETE WITH `CR-F0-001` CARRIED TO F1

Delivered through releases 1.0.19 and 1.0.20:

- proof-grounded company vocabulary learning before recurring Origin acquisition;
- Structure Learning before Bronze from already-fetched detail HTML;
- parser-family and structured identity evidence;
- Origin multi-location Bronze -> Silver projection foundation;
- current Employer-Origin-only review scope;
- sensor and stale/dead rows excluded from normal review while remaining auditable;
- source-local structured-identifier dedupe plus exact canonical Origin URL dedupe across Employer-Origin projections;
- independent `Published` and `First JAP observed`.

F0 is accepted under the cascading residual rule. `CR-F0-001` is part of F1 acceptance scope.

## F1 — Company -> Official Origin Jobspace Discovery — RELEASE QUALIFICATION ACTIVE — target release 1.0.21

Purpose: maximize the upstream multiplier: given only a company identity, find the official domain, careers/job space and likely ATS/job surface generically.

Bundled scope:

- evaluate public/open datasets and local libraries/reference implementations for company -> official website and careers/ATS discovery;
- inspect reusable ATS fingerprints, common careers URL patterns, structured metadata and public unauthenticated ATS endpoints;
- build the production capability natively/deterministically in JAP; no opaque hosted service becomes runtime authority;
- external/open libraries may be research/reference and may be adopted only when locally pinned, inspectable and replaceable;
- candidate company -> official domain -> careers surface -> ATS/portal fingerprint -> generic source proof handoff;
- impossible-control and host-bound validation remain fail-closed;
- classify discovery failures explicitly rather than hiding them;
- absorb `CR-F0-001` through generic vacancy identity/canonical evidence where it naturally overlaps with origin-space canonicalization; no FI-specific branch and no global locale-path stripping.

Implemented F1 release slice:

- existing `discover_origin_source` scorer/selection remains sole discovery authority;
- optional official-domain evidence can be provided from Wikidata P856 or explicit operator evidence and remains fail-soft/non-authoritative;
- bounded official-page parsing inspects URL-bearing HTML attributes only;
- ATS recognition is data-driven and employer-agnostic;
- discovered career/ATS surfaces are fed back through the existing JAP scoring/proof chain instead of creating a second resolver;
- generic detail evidence now supports page-declared canonical Origin URLs and explicitly labelled vacancy identifiers such as `Kennziffer`, `Job ID`, `Requisition ID`, `Reference Number`, and `Stellen-ID`, never free-number mining;
- review dedupe can use exact multi-key origin identity while retaining the prohibition on title/company fuzzy merging;
- `CR-F0-001` is regression-covered by the generic identity path.

Pre-release qualification truth:

- exact F1 head `26d6a4fb4e7cb942196b50e721745f3f51b0de1a` passed Pipeline CI, Pipeline re-entry target identity, P1 generic Employer-Origin systematic search, and P1 generic Employer-Origin product proof;
- operator chose to start the 1.0.21 release path after those product gates were green and not wait for the independent RCC Warmrunner Canary;
- desktop VERSION is now `1.0.21`; the final version-bumped PR head is being requalified before merge/release;
- PR #848 Warmrunner Canary is explicitly independent from this product release and is not a F1 release blocker.

F1 operator test 1.0.21:

- verify installed/About identity is 1.0.21;
- normal review remains free of stale/dead and market-sensor rows;
- inspect representative Employer-Origin jobs and original navigation;
- recheck `CR-F0-001` after fresh evidence can carry the new canonical/labelled vacancy identity;
- record any remaining bounded residual instead of forcing an additional release solely for cosmetic or non-critical cleanup.

Exit metric: measurable `company -> official domain -> careers space -> proof` coverage plus closure of the carried residual or an explicit operator reclassification.

## F2 — Origin Understanding + Parser-Family Scale-Out — target release 1.0.22

Purpose: turn proof-valid sources into productive sources without one connector per employer.

Bundled scope:

- run a real 10-20 company cohort through `proof -> vocabulary -> query-proven jobs -> structure learning -> Bronze -> parser family -> Silver`;
- persist/measure per-source learned vocabulary, search mechanism, parser family and field coverage;
- form parser families only from repeated independent source evidence or generic ATS/standard contracts;
- prefer JSON-LD/Microdata/generic DOM extraction;
- misunderstood sources remain explicit structure-learning evidence rather than receiving ad-hoc parser code;
- improve structured metadata, multi-location facts and source semantic understanding;
- expose stage-funnel counts and failure reasons.

Operator test: inspect multiple independent Origin families and real jobs; verify correct titles, employer, URL, published date and locations across more than one employer.

## F3 — Bronze -> Silver -> Gold Truth/Lifecycle Hardening — target release 1.0.23

Purpose: make downstream truth resistant to stale, dead and duplicate vacancies regardless of upstream family.

Bundled scope:

- exact current/dead/stale determination from Origin evidence, valid-through/publication and recurring observations;
- market sensors may support discovery/freshness diagnostics but never review authority;
- vacancy identity hierarchy: explicit structured requisition/vacancy identity -> canonical/final Origin identity -> exact canonical Origin URL -> bounded evidence equivalence only when safely proven; never title similarity alone;
- multi-location must not fork one vacancy;
- regression cohort across multiple Origin families;
- Product/CC consumes upstream truth instead of repairing it in UI code.

Operator test: current jobs remain, deliberately dead/stale jobs disappear from current review, sensor-only rows stay out, known safe aliases collapse, history remains auditable.

## F4 — Decision Intelligence Coverage — releases 1.0.24 and 1.0.25

### F4A — Profile Fit coverage — 1.0.24

Every current review job gets either an evidence-backed Jens<->Job Profile Fit or explicit `insufficient_evidence`; preliminary role affinity remains visibly separate.

Scope includes normalized Origin requirements, approved Candidate Facts, location/work model/commute, seniority, skills/capabilities and hard requirements, with factor-level explanations and coverage metrics.

### F4B — Ranking coverage — 1.0.25

Only fit-complete, lifecycle-current and hard-gate-qualified jobs become rankable. Every exclusion exposes a reason. Deterministic ranking remains authority; Top 5 comes from the complete eligible cohort.

Operator test: `current -> fit complete -> rankable -> Top 5` counts reconcile and sampled rankings have inspectable factor breakdowns.

## F5 — Application Lifecycle + Gmail-backed Outcome Tracking — release 1.0.26

Purpose: close the loop from discovered job to real application outcome.

Real seed evidence exists in Gmail from 2026-09-10 for:

- Finanz Informatik — `E362/B - AI Engineer / KI-Entwickler (m/w/d)`;
- enercity — `Data Engineer (m/w/d)`;
- ROSSMANN — `(Junior) Data Engineer (m/w/d) Logistics Business Analysis`, with multiple emails that must map to one application.

Scope:

- persisted application identity linked to canonical vacancy where possible;
- append-only application events: prepared/applied/receipt confirmed/interview/rejected/offer/withdrawn/follow-up;
- Gmail lifecycle evidence with provenance and no inferred submission without evidence;
- real `Applications` portfolio in CC;
- outcomes become later evaluation/learning evidence but do not rewrite deterministic ranking authority.

## F6 — Template-Authoritative Application Drafting — release 1.0.27

Purpose: reproduce the quality of chat-assisted applications while freezing approved layout/design.

Scope:

- approved template/layout becomes hash-bound authority;
- JAP mutates only explicitly editable content zones;
- Candidate Facts remain factual authority;
- wording derives from exact current Origin job evidence;
- render/layout validation proves unauthorized layout changes did not occur;
- human review remains mandatory; no automatic submit/send.

# Cross-cutting freeze invariants

- Maintain one funnel: `companies discovered -> official Origin found -> proof PASS -> vocabulary proven -> real jobs found -> structure understood -> Bronze -> Silver -> current -> fit complete -> rankable -> applied -> outcome`.
- Every stage exposes counts and classified failure/unknown reasons.
- Market sensors are discovery inputs, never Product review authority.
- Origin detail evidence outranks listing/search-card heuristics for vacancy facts.
- No one-employer parser merely to improve counts; parser families require repeated evidence or a generic standard/ATS contract.
- No fuzzy dedupe may suppress real vacancies without inspectable evidence.
- No ML/LLM layer becomes production decision authority during this deterministic freeze.
- No hosted external tool/service becomes a required runtime dependency for discovery or parsing.
- Operator feedback remains learning evidence, not direct ranking authority.
- Re-entry is updated at release/operator checkpoints with exact SHA/run evidence, measured funnel delta and carried residuals.

## Current repository/branch state

Canonical main: `b1360671658627f09d49b94f5bcadff7e5747674`.

Current implementation branch:

`agent/f1-origin-jobspace-discovery`

F1 is the sole mutating product package. Read-only research may run in parallel, but unrelated product mutations remain frozen.

## Sole next action

**Complete final 1.0.21 qualification on PR #855. If all release/product gates are green, squash-merge the exact tested head, let the immutable GitHub release and automatic local deploy complete, then run the combined F1 + `CR-F0-001` operator test.**
