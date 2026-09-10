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
- 1.0.20: exact Origin URL cross-source review dedupe merged as `b1360671658627f09d49b94f5bcadff7e5747674`; immutable release published; local deploy run `34475650818` PASS.
- 1.0.21: F1 jobspace-discovery capability merged as current release main `ad96becd0e5234102eeb38b42771b703705d42f4`; operator verified installed About `v1.0.21`, exact source revision `ad96becd0e52...`, DB truth green.

## F0 operator result — accepted with carried residual `CR-F0-001`

Observed PASS through 1.0.20/1.0.21:

- normal `All jobs` no longer shows stale/dead jobs;
- BA/StepStone/other market-sensor rows no longer appear as Product review jobs;
- `Published` and independent `First JAP observed` are both present;
- Employer-Origin rows remain visible and geography-eligible;
- exact same canonical Origin URLs can collapse across different Employer-Origin source projections.

Carried residual `CR-F0-001` remains OPEN after the 1.0.21 operator test:

- Finanz Informatik `Data Platform Engineer (m/w/d)` still appears twice through:
  - `https://www.f-i.de/karriere/offene-stellen/frankfurt/data-platform-engineer-m-w-d`
  - `https://www.f-i.de/de/karriere/offene-stellen/frankfurt/data-platform-engineer-m-w-d`
- do **not** solve this by globally stripping `/de/`, title/company fuzzy matching, or an FI-specific branch;
- generic labelled/canonical vacancy identity exists in code but the persisted rows still do not carry sufficient shared identity evidence to collapse this historical pair;
- carry into the 1.0.22 truth/cohort package and prove on fresh persisted evidence before closure.

Still deferred: no hard cutoff at 42% preliminary affinity; no date/location cosmetics; no Profile Fit or ranking changes yet.

# Frozen campaign execution policy

The package order remains frozen, but the release policy is optimized for development throughput rather than one release per minor residual.

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

## F0 — Origin Learning + Review Truth Foundation — COMPLETE WITH `CR-F0-001` CARRIED

Delivered through releases 1.0.19 and 1.0.20:

- proof-grounded company vocabulary learning before recurring Origin acquisition;
- Structure Learning before Bronze from already-fetched detail HTML;
- parser-family and structured identity evidence;
- Origin multi-location Bronze -> Silver projection foundation;
- current Employer-Origin-only review scope;
- sensor and stale/dead rows excluded from normal review while remaining auditable;
- source-local structured-identifier dedupe plus exact canonical Origin URL dedupe across Employer-Origin projections;
- independent `Published` and `First JAP observed`.

## F1 — Company -> Official Origin Jobspace Discovery — CAPABILITY SHIPPED, PRODUCT HANDOFF RESIDUAL CARRIED TO 1.0.22

Purpose: given only a company identity, find the official domain, careers/job space and likely ATS/job surface generically.

Shipped in 1.0.21:

- existing `discover_origin_source` scorer/selection remains sole discovery authority;
- optional official-domain evidence from Wikidata P856 or explicit operator evidence is fail-soft/non-authoritative;
- bounded official-page parsing inspects URL-bearing HTML attributes only;
- ATS recognition is data-driven and employer-agnostic;
- discovered career/ATS surfaces feed the existing JAP scoring/proof chain instead of a second resolver;
- generic detail evidence supports page-declared canonical Origin URLs and explicitly labelled vacancy identifiers such as `Kennziffer`, `Job ID`, `Requisition ID`, `Reference Number`, and `Stellen-ID`, never free-number mining;
- review dedupe supports exact multi-key Origin identity while retaining the prohibition on title/company fuzzy merging.

Exact pre-release PR head `6c2808d7eee0cb9c11061582235fa4b9949e7863` passed Pipeline CI, re-entry target identity, Windows Control Center contract, generic Employer-Origin systematic search and generic Employer-Origin product proof before #855 merged to `ad96becd0e5234102eeb38b42771b703705d42f4`.

### 1.0.21 operator finding

The installed release itself is healthy, but the **F1 product handoff is incomplete**:

- Sources still shows the pre-existing active Employer-Origin set (notably HDI, Finanz Informatik, Clarios, Hannover Rück plus pre-existing remote sources);
- no genuinely new company discovered by F1 is visible as a newly persisted/active Origin source in the Control Center;
- root cause: `run_origin_source_discovery_agent.py` intentionally remains read-only (`no candidate_url write`, `no source activation`, `no Bronze/Silver write`). The capability can discover a jobspace but 1.0.21 did not yet bridge strong F1 selections into the canonical candidate URL writer/proof/activation path;
- therefore the F1 exit metric is **not yet product-proven**, even though the discovery capability and release gates are technically green.

### Source reliability defect discovered during the same operator test

The Sources tab currently conflates lifecycle inventory and operational attention:

- inactive, unimplemented candidate inventory is represented as `connector_not_implemented`, causing the long tail to dominate `Needs attention`;
- `Active` currently proves only `search_profiles.is_active`, not job delivery;
- market sensors can visually sit beside Employer-Origin sources even though their semantics differ;
- existing backend truth already contains latest ingestion `total_loaded`/`inserted_count` plus Bronze/Silver history but the current UI does not make the activation-vs-delivery distinction sufficiently obvious.

Active remediation branch: `agent/source-reliability-truth`, based on 1.0.21 main `ad96becd0e5234102eeb38b42771b703705d42f4`.

Implemented on that branch so far:

- Source overview schema v3 distinguishes known/unimplemented inventory from operational blockers;
- inactive unimplemented candidates are no longer counted as `Needs attention` merely because implementation has not been selected;
- active Employer-Origin status exposes the exact latest ingestion load count (`active_last_run_N_jobs`) instead of presenting activation as delivery;
- market sensors expose explicit `market_sensor_active` status;
- summary truth adds Employer-Origin active, active-with-positive-latest-load and active-with-zero-latest-load counts;
- F1 persistence adapter `scripts/run_f1_origin_persistence_bridge.py` turns a strong F1 selection into replay evidence for **CAND-001**, which independently revalidates and remains the sole `candidate_url` writer; F1 itself receives no new write authority.

## F1/F2 combined 1.0.22 package — ACTIVE NEXT PACKAGE

The next release remains **1.0.22**. It intentionally combines the bounded F1 handoff/source-truth residuals with the previously planned F2 cohort instead of creating another release-only intermediate package.

Sole package objective:

`fresh company cohort -> F1 official domain/jobspace discovery -> CAND-001 persisted origin -> strict generic proof -> activation -> vocabulary -> query-proven real jobs -> structure learning -> Bronze -> parser family -> Silver -> reliable Sources/Product projection`

Required evidence before 1.0.22 release:

- run a real 10-20 company cohort, preferring companies not already active in JAP;
- measure `company -> F1 selected -> CAND-001 persisted -> proof=PASS -> active -> jobs observed -> Bronze -> Silver` funnel counts;
- classify every stop rather than hide it;
- Control Center Sources must visibly distinguish unimplemented inventory, operational attention, market sensors, active Employer-Origin with latest zero load, and active Employer-Origin with positive latest load;
- prove at least one genuinely fresh company reaches persisted/active Employer-Origin truth or explicitly classify the blocker preventing it;
- recheck `CR-F0-001` on fresh identity evidence; close it or explicitly reclassify at this checkpoint;
- no provider/company allowlist proliferation and no FI-specific parser branch.

Operator test for 1.0.22:

- inspect multiple independent Origin families and real jobs;
- verify correct titles, employer, Origin URL, published date and locations across more than one employer;
- verify the Sources tab accurately represents source role, activation and latest delivery evidence;
- verify newly discovered companies, if proof-valid, are actually visible as persisted/active sources rather than only as discovery reports;
- confirm sensor-only rows stay outside normal job review and known stale/dead rows remain excluded.

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
