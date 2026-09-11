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

Carried residual `CR-F0-001` remains OPEN:

- Finanz Informatik can expose the same real vacancy through parallel Origin aliases with and without `/de/`;
- do **not** solve this by globally stripping `/de/`, title/company fuzzy matching, or an FI-specific branch;
- generic labelled/canonical vacancy identity exists in code but persisted rows still do not consistently carry sufficient shared identity evidence to collapse historical aliases;
- fresh 1.0.22 cohort evidence in run `34569520523` still emitted parallel `/de/` and non-`/de/` FI vacancy URLs for multiple current postings, confirming that the residual remains real;
- **target closure package: F3 / 1.0.23**, because F3 already changes the vacancy-identity and lifecycle hierarchy. Close it there if the generic identity evidence is sufficient; otherwise explicitly reclassify it rather than adding an FI-specific exception.

Still deferred: no hard cutoff at 42% preliminary affinity; no date/location cosmetics; no Profile Fit or ranking changes yet.

# Frozen campaign execution policy

The package order remains frozen, but the release policy is optimized for development throughput rather than one release per minor residual.

Normal package flow:

`implementation -> focused tests -> Full Suite/Ruff/React/Windows contracts -> real Product/Origin proof where applicable -> merge exact tested head -> immutable Windows release -> automatic local deploy -> interactive operator test -> record evidence -> next package`

## Cascading residual rule

A package may advance after its main product objective is operator-proven even when a **bounded, understood, non-critical residual** remains. Such a residual is carried forward instead of forcing release-only churn or unrelated architecture work.

A residual may cascade only when all are true:

- it has a stable ID, origin package, concrete evidence, current risk classification and explicit open condition;
- it does not represent a security/credential issue, destructive/data-loss risk, irreversible migration problem or external side-effect boundary violation;
- the failure mode is visible and bounded rather than silently corrupting broad Product truth;
- it has a **next mandatory checkpoint** and either a semantically suitable target package or an explicit campaign-end closure gate;
- when a later package naturally touches the same architecture, that package must evaluate whether closing the residual is now cheaper/safer than carrying it again;
- any closure must add regression evidence appropriate to the failure mode before the residual can disappear from the ledger.

Residual carry discipline:

1. Every package checkpoint re-lists all inherited open residuals until each is closed or explicitly reclassified.
2. Prefer opportunistic closure when the relevant architecture is already being changed; do not create unrelated architecture churn merely to zero the residual count.
3. A residual may skip an unrelated implementation package only if its ledger entry names the next natural touchpoint and it remains visible in re-entry authority.
4. If no natural touchpoint occurs, the residual becomes a **mandatory campaign-end decision**: fix it, accept it as a documented product limitation, or explicitly move it to a separately authorized future campaign.
5. Residuals must never silently age out, lose their evidence trail, or hop indefinitely without a named checkpoint.

### Active residual ledger

- `CR-F0-001` — FI Origin alias identity duplication. Origin: F0. Current state: OPEN and freshly reconfirmed in run `34569520523`. Next natural touchpoint: **F3 vacancy identity/lifecycle hardening (1.0.23)**. Mandatory decision no later than F3 operator checkpoint.
- `CR-F1-001` — fresh company identity -> F1 discovery -> CAND-001 persistence -> proof/activation has not yet been product-proven end-to-end. Origin: F1. Current evidence: run `34565632246` had 11 `f1_not_found`; Windhoff was selected but CAND-001 returned `manual_review_required`, so no new candidate URL was written. F2 proves the downstream persisted-source path independently with Nortal, but does not erase this upstream F1 residual. Opportunistic closure: any later work that naturally touches company discovery/persistence. Otherwise mandatory campaign-end decision.

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

## F1 — Company -> Official Origin Jobspace Discovery — CAPABILITY SHIPPED, `CR-F1-001` CARRIED

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

### 1.0.21 operator finding and current carry

The installed 1.0.21 release itself is healthy. The source-reliability and F1 persistence adapter were subsequently merged on main in #858, with CAND-001 remaining the sole candidate-url writer.

The remaining F1 gap is no longer a missing write bridge; it is the unproven **fresh-company end-to-end discovery/persistence outcome** recorded as `CR-F1-001`:

- real 12-company run `34565632246` produced 11 `f1_not_found` results;
- Windhoff was the only F1 selection (`https://windhoff-karriere.de/`) but CAND-001 classified it `manual_review_required`;
- therefore that run produced `persisted_or_ready=0` and `candidate_url_written=0`;
- this is accepted as a bounded upstream residual for 1.0.22 because the downstream persisted-source path is now independently product-proven, but it remains in the residual ledger until a fresh-company path succeeds or the campaign-end decision explicitly accepts/reclassifies the limitation.

### Source reliability remediation already merged to main

Main `b5cca02ab23766dda43b49cfdc54b8517cfb36dc` / PR #858 provides:

- Source overview schema v3 distinguishes known/unimplemented inventory from operational blockers;
- inactive unimplemented candidates are no longer counted as `Needs attention` merely because implementation has not been selected;
- active Employer-Origin status exposes the exact latest ingestion load count (`active_last_run_N_jobs`) instead of presenting activation as delivery;
- market sensors expose explicit `market_sensor_active` status;
- summary truth adds Employer-Origin active, active-with-positive-latest-load and active-with-zero-latest-load counts;
- F1 persistence adapter `scripts/run_f1_origin_persistence_bridge.py` turns a strong F1 selection into replay evidence for **CAND-001**, which independently revalidates and remains the sole `candidate_url` writer; F1 itself receives no new write authority.

## F1/F2 combined 1.0.22 package — RELEASE QUALIFICATION NEXT

The next release remains **1.0.22**. It combines the bounded F1 carry/source-truth work with the F2 cohort and Dynamic-Origin hardening.

Package objective:

`fresh/persisted company cohort -> canonical candidate truth -> strict generic proof -> activation -> vocabulary/search -> query-proven real jobs when available -> structure learning -> Bronze -> parser family -> Silver -> reliable Sources/Product projection`

### F2 branch effect proof — PASS on 2026-09-11

Branch evidence is non-canonical until normal merge/release, but the required source-admission E2E is now proven.

Qualified Dynamic-Origin hardening:

- generic Dynamic-Origin evidence is integrated into `employer_origin_acquisition_v4`; route/API evidence may create bounded candidates but never substitutes for strict genuine-job detail proof;
- strong delegated detail redirects are rebound only within generic provider identity boundaries; unrelated redirect hosts remain rejected;
- explicit `/jobposting/<opaque-id>/apply` evidence may derive the corresponding parent detail candidate without inventing an ID;
- no employer-specific Nortal/TRIOLOGY/Valuny branches or allowlists were introduced;
- malformed URL literals remain fail-closed;
- focused hardening qualifier: **28 tests PASS + Ruff PASS**; qualified product commit `036faf8d`;
- activation projection hygiene deactivates stale `generic_origin:*` execution profiles before re-projecting the complete proof cohort, with a contract regression preventing the prior 26-vs-24 stale-profile state.

Real effect run `34569520523` on exact head `de7e48dcbb59cef375109a829c37bb1bb31ad49a` completed **SUCCESS**:

- selected persisted-inactive cohort: 8 companies (`nortal`, `triology`, `valuny`, `hdi`, `the_associated_engineers`, `bjak`, `land_niedersachsen`, `trustyou`);
- complete canonical product evaluation: 66 candidates, **25 `proof=PASS`**;
- exactly one selected cohort member passed proof: **Nortal**;
- activation after apply: `GENERIC_ACTIVE_PROFILES_AFTER=25` and `GENERIC_ACTIVE_SOURCE_PROJECTION_AFTER=25`;
- selected-cohort funnel: `proof_pass=1`, `active=1`, `successful_run=1`, `delivering_now=0`, `bronze_sources=0`, `silver_sources=0`;
- Nortal result: `proof=True|active=True|run=success|loaded=0|inserted=0|bronze=0|silver=0`;
- the zero-load result is **not a source-validity residual**: the frozen contract explicitly permits a valid source to return zero current jobs. It remains observable as active-with-zero-latest-load in Sources rather than being misrepresented as delivery;
- TRIOLOGY stopped at inventory evidence; Valuny stopped at final strict proof; both remain ordinary classified long-tail misses, not company-specific exceptions.

This opens the branch-level source-admission Operator gate: a previously persisted inactive Dynamic-Origin company has now reached `proof=PASS -> active -> successful recurring generic-origin ingestion`. The 1.0.22 package is **not yet release authority** until the normal qualification/merge/release/deploy/operator sequence completes.

### Residual disposition at the 1.0.22 checkpoint

- `CR-F0-001`: still OPEN; fresh FI alias evidence reconfirms it. Carry to F3 because F3 already changes vacancy identity/lifecycle semantics.
- `CR-F1-001`: OPEN; downstream source onboarding is now proven with Nortal, but fresh company -> F1 -> CAND-001 persistence is still not product-proven. Keep it in the ledger; close opportunistically if discovery/persistence architecture is touched again, otherwise force a campaign-end decision.
- No new residual is created for Nortal zero delivery; zero current jobs is an explicitly valid source state.

Required evidence before 1.0.22 release:

- branch effect proof above: **PASS**;
- Control Center source-role/activation/latest-delivery truth: already merged on main in #858, requalify with final package head;
- final Full Suite/Ruff/React/Windows contracts on the exact release-candidate head;
- recheck that no provider/company allowlist proliferation or FI-specific parser branch entered the package;
- merge the exact qualified head, publish immutable 1.0.22, prove automatic local deploy, then run the interactive operator test.

Operator test for 1.0.22:

- inspect multiple independent Origin families and real jobs;
- verify correct titles, employer, Origin URL, published date and locations across more than one employer;
- verify Sources accurately represents source role, activation and latest delivery evidence, including Nortal as active with zero latest load unless jobs appear later;
- verify the newly proof-valid Nortal source is visible as persisted/active rather than only as discovery evidence;
- confirm sensor-only rows stay outside normal job review and known stale/dead rows remain excluded;
- confirm the residual ledger is carried unchanged into the next package authority unless an item is explicitly closed with regression evidence.

Sole next action: qualify the exact 1.0.22 release-candidate head with Full Suite/Ruff/React/Windows contracts and package-specific Origin checks. If green, merge that exact head to main, publish/deploy 1.0.22 and perform the interactive operator test before entering F3.

## F3 — Bronze -> Silver -> Gold Truth/Lifecycle Hardening — target release 1.0.23

Purpose: make downstream truth resistant to stale, dead and duplicate vacancies regardless of upstream family.

Inherited residuals at F3 entry:

- `CR-F0-001` is an explicit F3 closure target because this package already changes vacancy identity and lifecycle truth;
- `CR-F1-001` remains visible in the ledger but does not force unrelated F3 discovery changes; only close it here if F3 work naturally touches company discovery/persistence, otherwise carry it to the next named checkpoint/campaign-end gate.

Bundled scope:

- exact current/dead/stale determination from Origin evidence, valid-through/publication and recurring observations;
- market sensors may support discovery/freshness diagnostics but never review authority;
- vacancy identity hierarchy: explicit structured requisition/vacancy identity -> canonical/final Origin identity -> exact canonical Origin URL -> bounded evidence equivalence only when safely proven; never title similarity alone;
- multi-location must not fork one vacancy;
- regression cohort across multiple Origin families;
- Product/CC consumes upstream truth instead of repairing it in UI code.

Operator test: current jobs remain, deliberately dead/stale jobs disappear from current review, sensor-only rows stay out, known safe aliases collapse, history remains auditable. `CR-F0-001` must be closed or explicitly reclassified at this checkpoint; all still-open inherited residuals must remain present in the ledger.

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
