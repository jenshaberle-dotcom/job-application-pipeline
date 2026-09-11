# JAP Current Re-Entry

Status: canonical current re-entry projection + frozen product campaign sequencing authority

Read this file from canonical `refs/heads/main` before continuing product work. `docs/current/README.md` remains useful general operational context, but this file is the sequencing authority where older text conflicts with it.

## Live repository checkpoint — 2026-09-11

Canonical `main` is `dfd8cc3e40c84ddd4bb0374708d1da0ffa2c19e0` after #861. The latest published Windows release is **JAP Control Center Desktop v1.0.22**, sourced from `bb12e62a4fb638fdf782a0401ed54d5fe9922221` / PR #859.

The active F2 closure is **PR #862**, still Draft and mergeable, with exact head `e301bb4ecc69e0c4261f7357f640f8c16bf62ad0`. Its Windows `VERSION` is **1.0.23**. Therefore older text that still calls 1.0.22 the next release is stale, and the downstream release labels are shifted by one patch: F2 closure targets 1.0.23; F3 starts no earlier than 1.0.24.

The immediately preceding #862 head `31fce4cf3dd64bbaa3bbdc45971d89c73ce9c2a3` had Pipeline CI `34605882832` PASS, P1 generic Employer-Origin product proof `34605882293` PASS, JAP Windows Control Center contract `34605882404` PASS, and re-entry identity PASS, but it had **no** valid `F2 B-ITE VALUNY real acceptance` run. Historical/assumed run `34605882197` is not evidence for that head.

Head `e301bb4ecc69e0c4261f7357f640f8c16bf62ad0` closes that acceptance-definition gap. The branch-local `.github/workflows/f2-bite-valuny-e2e.yml` now binds the product proof to the fresh VALUNY ingestion run: exact checkout -> persisted VALUNY origin -> canonical `proof=PASS` -> activation -> recurring ingestion with `loaded > 0` -> Bronze rows from that run -> Silver rows joined to those fresh Bronze rows -> matching Gold/Product-readiness rows -> matching canonical Control Center `job_readiness` rows with title and Origin URL. The Jobs UI, including `All observed`, renders this canonical `job_readiness` payload.

Real exact-head acceptance run **`34632254867`** started automatically from `e301bb4ecc69e0c4261f7357f640f8c16bf62ad0`. At this checkpoint exact checkout, RCC runtime context, product DB environment, pinned local OSS runtime and persisted VALUNY origin state are PASS; the canonical product recomputation is still running. The same head also started fresh Pipeline CI, P1 product proof, Windows contract and re-entry identity checks. **No release/merge authority is inferred until the real acceptance and the required exact-head qualification checks complete successfully.**

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
- 1.0.21: F1 jobspace-discovery capability merged as `ad96becd0e5234102eeb38b42771b703705d42f4`; operator verified installed About `v1.0.21`, exact source revision `ad96becd0e52...`, DB truth green.
- 1.0.22: F2 Dynamic-Origin hardening and real persisted cohort merged through PR #859 as `bb12e62a4fb638fdf782a0401ed54d5fe9922221`; Desktop v1.0.22 is published from that exact commit.
- 1.0.23: reserved by active F2 closure PR #862; **not release-authorized yet**.

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
- **target closure package: F3**, because F3 already changes the vacancy-identity and lifecycle hierarchy. Close it there if the generic identity evidence is sufficient; otherwise explicitly reclassify it rather than adding an FI-specific exception.

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

- `CR-F0-001` — FI Origin alias identity duplication. Origin: F0. Current state: OPEN and freshly reconfirmed in run `34569520523`. Next natural touchpoint: **F3 vacancy identity/lifecycle hardening**. Mandatory decision no later than the F3 operator checkpoint.
- `CR-F1-001` — fresh company identity -> F1 discovery -> CAND-001 persistence -> proof/activation has not yet been product-proven end-to-end. Origin: F1. Current evidence: run `34565632246` had 11 `f1_not_found`; Windhoff was selected but CAND-001 returned `manual_review_required`, so no new candidate URL was written. F2 proves the downstream persisted-source path independently, but does not erase this upstream F1 residual. Opportunistic closure: any later work that naturally touches company discovery/persistence. Otherwise mandatory campaign-end decision.
- `CR-F2-001` — F2 positive-delivery/Product closure. Origin: F2. Earlier activation-verifier failures must not be conflated with genuine delivery failure. Current open condition: exact final #862 head must produce a fresh real VALUNY acceptance proving canonical `proof=PASS -> active -> recurring ingestion with loaded > 0 -> fresh Bronze > 0 -> fresh Silver > 0 -> matching Gold/Product readiness > 0 -> matching canonical Control Center / Jobs All observed projection`. Head `e301bb4ecc69e0c4261f7357f640f8c16bf62ad0` contains this full gate and run `34632254867` is executing it, but no PASS is recorded at this checkpoint. Mandatory closure: before #862 leaves Draft / before v1.0.23 release authority.

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
- this is accepted as a bounded upstream residual because the downstream persisted-source path is independently product-proven, but it remains in the residual ledger until a fresh-company path succeeds or the campaign-end decision explicitly accepts/reclassifies the limitation.

### Source reliability remediation already merged to main

Main `b5cca02ab23766dda43b49cfdc54b8517cfb36dc` / PR #858 provides:

- Source overview schema v3 distinguishes known/unimplemented inventory from operational blockers;
- inactive unimplemented candidates are no longer counted as `Needs attention` merely because implementation has not been selected;
- active Employer-Origin status exposes the exact latest ingestion load count (`active_last_run_N_jobs`) instead of presenting activation as delivery;
- market sensors expose explicit `market_sensor_active` status;
- summary truth adds Employer-Origin active, active-with-positive-latest-load and active-with-zero-latest-load counts;
- F1 persistence adapter `scripts/run_f1_origin_persistence_bridge.py` turns a strong F1 selection into replay evidence for **CAND-001**, which independently revalidates and remains the sole `candidate_url` writer; F1 itself receives no new write authority.

## F2 — Dynamic-Origin + B-ITE product closure — 1.0.22 SHIPPED, 1.0.23 CLOSURE ACTIVE

The original 1.0.22 package shipped through PR #859 / `bb12e62a4fb638fdf782a0401ed54d5fe9922221`. Its branch evidence established generic Dynamic-Origin source admission and compatibility without provider/company-specific allowlists.

Package objective remains:

`fresh/persisted company cohort -> canonical candidate truth -> strict generic proof -> activation -> vocabulary/search -> query-proven real jobs when available -> structure learning -> Bronze -> parser family -> Silver -> Gold/Product -> reliable Sources/Control Center projection`

### 1.0.22 Dynamic-Origin evidence — PASS for source admission

Real effect run `34569520523` on exact head `de7e48dcbb59cef375109a829c37bb1bb31ad49a` completed SUCCESS:

- selected persisted-inactive cohort: 8 companies (`nortal`, `triology`, `valuny`, `hdi`, `the_associated_engineers`, `bjak`, `land_niedersachsen`, `trustyou`);
- complete canonical product evaluation: 66 candidates, 25 `proof=PASS`;
- exactly one selected cohort member passed proof: Nortal;
- activation after apply: `GENERIC_ACTIVE_PROFILES_AFTER=25` and `GENERIC_ACTIVE_SOURCE_PROJECTION_AFTER=25`;
- selected-cohort funnel: `proof_pass=1`, `active=1`, `successful_run=1`, `delivering_now=0`, `bronze_sources=0`, `silver_sources=0`;
- Nortal result: `proof=True|active=True|run=success|loaded=0|inserted=0|bronze=0|silver=0`;
- zero current jobs is valid source state and is not itself a source-validity residual;
- TRIOLOGY stopped at inventory evidence; Valuny stopped at final strict proof in that older cohort run.

Full-suite compatibility hardening also passed: static-first shadowing preserves established static/query/anchor/listing authority, and one-shot run `34571596584` passed Ruff plus **3211/3211** Python tests.

### PR #862 — current F2 closure boundary

PR #862 carries employer-backed B-ITE evidence through the existing generic-origin product path without a VALUNY-specific vacancy parser or provider allowlist. Current head: `e301bb4ecc69e0c4261f7357f640f8c16bf62ad0`; current target version: 1.0.23.

The predecessor head `31fce4cf3dd64bbaa3bbdc45971d89c73ce9c2a3` already proved the unchanged implementation with Pipeline CI, P1 generic Employer-Origin product proof, Windows Control Center contract and re-entry identity. The new `e301bb4...` commit changes only the dedicated acceptance workflow so that the final product boundary is no longer inferred from historical or unrelated rows.

Exact-head qualification now in flight on `e301bb4ecc69e0c4261f7357f640f8c16bf62ad0`:

- real F2 B-ITE VALUNY acceptance `34632254867` — started automatically from the workflow change; early runtime/state prerequisites PASS, canonical product recomputation in progress at this checkpoint;
- fresh Pipeline CI `34632261569` — started;
- fresh P1 generic Employer-Origin product proof `34632261239` — started;
- fresh JAP Windows Control Center contract `34632261201` — started;
- fresh re-entry identity checks — started.

The acceptance is now intentionally stronger than the earlier branch gate. It requires at least one VALUNY row from the **latest exact ingestion run** to survive Bronze -> Silver -> Gold/Product readiness and appear in the canonical Control Center `job_readiness` payload with a title and `https://` Origin URL. Because the Jobs screen and its `All observed` filter render `payload.job_readiness`, this is the automated Product/UI projection gate; the installed desktop still receives its own operator test after release.

### Residual disposition at the current F2 checkpoint

- `CR-F0-001`: OPEN; carry to F3 vacancy identity/lifecycle hardening.
- `CR-F1-001`: OPEN; downstream source onboarding does not erase the missing fresh-company F1 -> CAND-001 persistence proof.
- `CR-F2-001`: OPEN while run `34632254867` and the exact-head qualification set remain unaccepted; close only after positive VALUNY delivery plus fresh Bronze/Silver/Gold and canonical Jobs projection PASS on the final #862 head.

Sole next action: **evaluate run `34632254867` and the fresh exact-head qualification set for `e301bb4ecc69e0c4261f7357f640f8c16bf62ad0`.** If the real acceptance fails, fix only the concrete evidence/product-boundary defect and rerun on the resulting exact head. If the acceptance and required CI are green, close `CR-F2-001`, mark #862 ready, merge the exact qualified head, wait for main CI, publish immutable v1.0.23, prove automatic local deployment, and perform the interactive operator test before entering F3. Do not merge or publish before those gates pass.

## F3 — Bronze -> Silver -> Gold Truth/Lifecycle Hardening — target release 1.0.24

Purpose: make downstream truth resistant to stale, dead and duplicate vacancies regardless of upstream family.

Inherited residuals at F3 entry:

- `CR-F0-001` is an explicit F3 closure target because this package already changes vacancy identity and lifecycle truth;
- `CR-F1-001` remains visible in the ledger but does not force unrelated F3 discovery changes; only close it here if F3 work naturally touches company discovery/persistence, otherwise carry it to the next named checkpoint/campaign-end gate;
- `CR-F2-001` must already be closed before F3 entry because it is a release gate for #862/v1.0.23, not a cascade candidate.

Bundled scope:

- exact current/dead/stale determination from Origin evidence, valid-through/publication and recurring observations;
- market sensors may support discovery/freshness diagnostics but never review authority;
- vacancy identity hierarchy: explicit structured requisition/vacancy identity -> canonical/final Origin identity -> exact canonical Origin URL -> bounded evidence equivalence only when safely proven; never title similarity alone;
- multi-location must not fork one vacancy;
- regression cohort across multiple Origin families;
- Product/CC consumes upstream truth instead of repairing it in UI code.

Operator test: current jobs remain, deliberately dead/stale jobs disappear from current review, sensor-only rows stay out, known safe aliases collapse, history remains auditable. `CR-F0-001` must be closed or explicitly reclassified at this checkpoint; all still-open inherited residuals must remain present in the ledger.

## F4 — Decision Intelligence Coverage — releases 1.0.25 and 1.0.26

### F4A — Profile Fit coverage — 1.0.25

Every current review job gets either an evidence-backed Jens<->Job Profile Fit or explicit `insufficient_evidence`; preliminary role affinity remains visibly separate.

Scope includes normalized Origin requirements, approved Candidate Facts, location/work model/commute, seniority, skills/capabilities and hard requirements, with factor-level explanations and coverage metrics.

### F4B — Ranking coverage — 1.0.26

Only fit-complete, lifecycle-current and hard-gate-qualified jobs become rankable. Every exclusion exposes a reason. Deterministic ranking remains authority; Top 5 comes from the complete eligible cohort.

Operator test: `current -> fit complete -> rankable -> Top 5` counts reconcile and sampled rankings have inspectable factor breakdowns.

## F5 — Application Lifecycle + Gmail-backed Outcome Tracking — release 1.0.27

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

## F6 — Template-Authoritative Application Drafting — release 1.0.28

Purpose: reproduce the quality of chat-assisted applications while freezing approved layout/design.

Scope:

- approved template/layout becomes hash-bound authority;
- JAP mutates only explicitly editable content zones;
- Candidate Facts remain factual authority;
- wording derives from exact current Origin job evidence;
- render/layout validation proves unauthorized layout changes did not occur;
- human review remains mandatory; no automatic submit/send.