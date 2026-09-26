# Freeze II — Source Truth & Connector Reliability

Status: ACTIVE — S0 COMPLETE; LINKEDIN + INDEED SENSOR EXPANSION FIRST
Canonical issue: #1038
Previous campaign: F0-F6 COMPLETE / OPERATOR ACCEPTED FOR CURRENT COHORT

## Mission

The next JAP freeze campaign deliberately moves upstream.

Primary loop:

`LinkedIn + Indeed conservative market sensors -> new employer/source candidates -> freeze expanded candidate cohort -> generic connector creation -> systematic live search -> broader real vacancy evidence -> better company/source understanding -> stronger metadata extraction -> optional first ML shadow model -> reassess`

The campaign does not begin by adding ranking, Fit, UI or application features. The present learning bottleneck is evidence breadth. The existing candidate set exists because each candidate has already produced at least one historically relevant job/discovery signal. Freeze II therefore first expands that population with conservative market sensors and only then freezes the connector-fleet denominator. Historical relevance justifies monitoring effort but does not itself prove a current vacancy or current source validity.

## Inherited work

- #789: Discovery -> Employer-Origin -> connector breadth.
- #676: ACQ-GENERALIZATION-90 reusable deterministic builder architecture. Its historical 36/65 metric is retained evidence, not current authority.
- CR-F1-001: fresh company -> F1 discovery -> CAND-001 persistence -> proof/activation.
- F4A-R2/R3: source-to-Silver-to-operator evidence and layer-loss discipline.
- F4A-R7: requirement-section and skill-evidence reliability.
- #891: generic skill extraction + capability Fit/Combined, now admitted only after upstream evidence broadens.
- #910: Data-Layers truth audit is relevant; broad visual simplification stays secondary.
- #917: unknown mailbox jobs may later become bounded acquisition inputs but never bypass Origin proof.
- #922: manual notebook remains observation-only backlog.
- #1035: updater hardening remains an operational canary and is not Freeze-II scope.

## Frozen truth boundaries

1. Employer-Origin or separately reviewed equivalent is Product source authority. Aggregators/sensors remain discovery evidence.
2. **Technical connector completeness and Product source coverage are separate metrics.** A connector may become technically complete after a deterministic synthetic smoke fixture plus a successful live search execution. Product/source coverage still changes only after real Employer-Origin evidence and unchanged strict genuine-job E2E proof.
3. A synthetic/dummy smoke job exists only to prove the common connector interface. It must be explicitly synthetic, deterministic, non-persistable and hard-blocked from Bronze, Silver, Product/CC, ranking and application authority.
4. Source identity, reachability, inventory completeness, detail identity and field extraction are separate dimensions. A live search that reaches and exhausts the source but yields no currently relevant vacancy is a valid zero-yield search result, not a connector failure.
5. Missing/conflicting metadata remains explicit unknown/conflict.
6. Bronze preserves evidence; Silver owns canonical normalized field truth; Product/CC may not manufacture stronger downstream truth.
7. Field provenance must survive to the operator surface.
8. Per-candidate connector configuration/instances are allowed because the fleet is candidate-scoped; parsing, discovery and extraction mechanics must still be generalized into reusable source/template-family capabilities rather than employer-name branches.
9. Deterministic structured or bounded visible evidence is first lane.
10. ML/LLM may later propose Shadow evidence only; neither creates source truth.
11. Fit/Combined/ranking authority does not expand until upstream gates pass.
12. LinkedIn and Indeed are discovery/freshness sensors only. Direct login automation, browser-session automation, CAPTCHA handling, broad scraping and raw job-content persistence remain prohibited. Their admissible automated transport is a separately reviewed official API or an already-approved external web-search provider that returns minimal public search evidence.
13. LinkedIn/Indeed observations may create or prioritize employer/source candidates only. Aggregator URLs and job identities are discarded before Employer-Origin learning; the candidate must be resolved to a direct employer/ATS source before source proof.
14. Candidate expansion precedes the connector-fleet denominator freeze. The S0 count of 67 is the initial population, not the final S1 denominator.

## S0 — Current truth baseline + layer-loss map — COMPLETE

Read-only current-state measurement.

Required measurements:

- current Employer-Origin candidate population;
- source/connector lifecycle overview;
- active Employer-Origin count and family concentration;
- deterministic builder first-failure distribution:
  `identity -> origin -> origin_reachability -> delegation -> provider -> inventory -> detail -> proof -> recipe`;
- Product/CC review cohort by source family;
- Bronze -> Silver -> Product/CC field status/coverage;
- requirement-section and skill recall by source;
- Silver -> Product/CC projection loss;
- explicit origin-unavailable and extractor-gap cohorts.

S0 composes existing qualified audit paths instead of creating a competing truth stack:

- `run_deterministic_connector_builder_layer_audit_v6`;
- `run_f4a_r3_bronze2e_requirement_audit`;
- `run_f4a_r7_skill_reliability_audit`;
- current `source_connector_overview`.

The wrapper is `scripts/run_freeze2_s0_source_truth_baseline.py`.

Important: builder `recipe_ready` remains diagnostic and is explicitly not Product coverage.

Exact-main S0 evidence (2026-09-25):

- source SHA: `fe7758d2fb7dbed4586fdc55af69969ad37f7547`;
- workflow run: `36187566852` — SUCCESS;
- source overview: 89 sources, 31 Employer-Origin, 21 active Employer-Origin, 22 validated, 33 registered, 39 ingested;
- active Employer-Origin family concentration: 21/21 current active Employer-Origin sources are projected through `generic_origin`;
- current deterministic connector-candidate population: 67;
- V6 diagnostic recipe-ready: 23/67 — diagnostic only, not Product coverage;
- first failures: Origin 16, Origin reachability 1, Inventory 6, Detail 13, Proof 8;
- Product review source families: generic_origin 41, finanz_informatik 14, personio 12, hdi 9, enercity 2;
- current metadata audit: 75 reachable rows, 0 extractor-gap rows, 0 Silver->Product/CC projection-loss rows, 0 violating rows;
- requirement/skill audit: 53 bounded requirement sections, 54 jobs with observed skills, 16 skill-recall-risk rows;
- field coverage pressure remains high even without layer-loss: employment type source-absent 72, languages source-absent 49, seniority source-absent 73, weekly hours source-absent 55, work model source-absent 28 plus 3 conflicts;
- all S0 effect boundaries remained zero.

Interpretation: downstream projection integrity is currently healthy; the next leverage lies in broader Origin/connector coverage plus stronger reusable extraction at the source/detail boundary. S0 therefore closes and S1/S2 move into residual classification before any activation.

S0 boundary:

- DB writes 0;
- source activation 0;
- connector registration 0;
- Bronze/Silver/Product writes 0;
- provider/LLM calls 0;
- Fit/ranking/application authority 0.

## S0.5 — Conservative market-sensor expansion — FIRST ACTIVE SLICE

Add **LinkedIn** and **Indeed** as conservative market-discovery sensors alongside Bundesagentur and StepStone.

Purpose:

- broaden company/employer discovery;
- broaden role/title/vocabulary visibility;
- detect false-negative employers that the current source raster misses;
- feed candidate expansion, never Product job authority.

Transport contract:

- no personal login/session automation;
- no browser automation or CAPTCHA bypass;
- no direct broad scraping;
- no raw job-description persistence;
- use only a documented/approved API path or the project's already-approved bounded web-search provider path;
- emit only minimal discovery evidence: platform, query, observed company, bounded title/location signal, public result URL/reference, observed timestamp;
- discard aggregator URL/job identity before Employer-Origin URL-structure learning.

Initial acceptance:

- LinkedIn and Indeed both execute one bounded search plan for the current role/location intent;
- each produces an explicit outcome: observations, zero-yield, provider-unavailable or policy-blocked;
- provider request count and budget are explicit;
- DB/Bronze/Silver/Product writes remain zero in the first proof.

## S0.6 — Candidate expansion from sensor evidence

After sensor proof, run known-candidate suppression and bounded candidate promotion:

- suppress companies already represented by the Employer-Origin candidate lifecycle;
- retain genuinely new employers for bounded review/promotion;
- resolve each promoted company to a direct employer/ATS source before any Origin proof;
- preserve discovery provenance (`linkedin`, `indeed`, existing sensors) without allowing the aggregator URL to become source authority.

The resulting reviewed candidate population becomes the **Freeze-II connector-fleet denominator**.

The current S0 count **67** remains the initial baseline for delta accounting. New sensor-derived candidates are added explicitly; candidates are never removed merely to improve a percentage.

## S1 — Connector fleet completeness + systematic live search — PRIMARY

Primary work: #789 + CR-F1-001.

S0 measured **67 initial connector candidates**. S0.5/S0.6 may grow that population. Once the sensor-driven candidate-expansion wave is reviewed, S1 freezes the expanded cohort as its denominator. S1 is not satisfied by a convenient subset. The target is fleet completeness, with **~95% generic connector-generation success as a strong engineering objective (not a hard gate)** and eventual connector smoke coverage for the full frozen cohort.

### S1-A — executable connector contract

For every candidate in the S0 baseline cohort:

- a materialized connector instance/configuration exists behind the common connector interface;
- a deterministic **synthetic smoke mode** returns at least one canonical dummy job/observation so interface wiring, normalization shape and orchestration can be proven even when the live source currently has zero relevant vacancies;
- every synthetic record is marked non-authoritative and is structurally blocked from Bronze, Silver, Product/CC, ranking, Fit and application paths;
- shared ATS/source-family mechanics are reused wherever possible; a per-candidate configuration is not an excuse for employer-specific parsing logic.

Acceptance metrics:

- `generic_builder_success_rate`: fraction of the frozen expanded cohort whose connector instance/configuration is generated without employer-specific runtime parsing code;
- **~95%** generic builder success is a strong target and design pressure, not a hard pass/fail threshold;
- difficult candidates may not be removed from the denominator to improve the rate;
- remaining long-tail cases are classified by reusable source/ATS mechanics and closed separately;
- eventual technical connector-smoke coverage target remains **100% of the frozen cohort**.

### S1-B — live source search

Smoke success is not completion. Every connector must then execute against its live authoritative source and systematically search/enumerate the available vacancy space using the normal bounded acquisition contract.

A live run ends in one of these explicit states:

- `live_search_pass_jobs`: source searched and real vacancies observed;
- `live_search_pass_zero_yield`: source searched successfully but no currently relevant vacancy was found;
- `live_search_blocked`: source/reachability/inventory mechanics still unresolved;
- `live_search_failed`: connector/runtime defect.

Zero yield is acceptable; an unimplemented or unsearched candidate is not.

Every real vacancy remains subject to exact Employer-Origin/detail identity and unchanged strict genuine-job proof before it can become Bronze/Product evidence. The historical fact that a candidate once yielded a relevant job explains why it belongs in the fleet; it does not bypass current proof.

### S1-C — relevance sweep and evidence breadth

After technical fleet completeness:

- run every connector systematically against the current job profile/search policy;
- retain per-candidate search status, source-family, observed inventory count, relevant-job count and zero-yield reason;
- feed only real proven jobs through normal Bronze/Silver ingestion;
- use the resulting cross-family vacancy cohort as the evidence base for S3 metadata/extraction hardening.

The #676 >=90% strict Product-coverage target remains useful as a separate source-validity metric, but it must not be confused with the S1 **connector-fleet completeness target of 100%**.

## S2 — Source-family capability matrix

For every material source/ATS family record:

- first-party/canonical-host relationship;
- delegation model;
- inventory transport/completeness/pagination;
- SPA/API behavior;
- stable vacancy identifier;
- canonical/detail/apply URL semantics;
- closure evidence;
- structured JobPosting support;
- bounded visible-text fallback;
- parser family;
- field strengths/gaps;
- activation proof contract.

Unknown family behavior stays explicit.

## S3 — Deterministic extraction hardening

Priority fields:

- title;
- company identity;
- location/multi-location;
- workplace type;
- employment type;
- dates/validity;
- compensation;
- vacancy identifier;
- canonical/detail/apply URL;
- bounded description;
- requirement sections.

Structured evidence must be exact/coherent. Bounded visible text may fill gaps only with provenance. Conflicts become `conflict`; generic page body, navigation and cookie chrome cannot establish a field.

## S4 — Bronze -> Silver -> Product/CC integrity

For each supported field:

`Origin evidence -> Bronze detail_evidence -> Silver canonical evidence -> Product projection -> JAP CC`

Acceptance:

- known false-confident Product metadata = 0;
- Silver -> Product/CC projection loss = 0;
- unknown/conflict preserved;
- every percentage has named numerator/denominator/cohort;
- source-family and field-level diagnostics remain inspectable.

## S5 — Metadata learning + optional first ML shadow model

S3/S4 first build a materially broader, provenance-rich dataset from the expanded connector fleet. Only then evaluate whether evidence volume and reviewed labels justify a first ML training experiment.

ML admission checklist:

- training examples come from reviewed source-held evidence, not model-generated truth;
- train/validation/test splits are held out by employer/source family where practical;
- deterministic extraction remains production authority;
- the first model runs in Shadow and reports precision/recall/error classes against reviewed labels;
- no ML prediction may silently fill a missing source field;
- promotion requires evidence that it improves a defined residual task without regressing deterministic precision.

Good first tasks are narrow residual classification/extraction problems such as requirement-line classification, skill-span candidates, work-model classification or source/template-family classification. Do not start with a monolithic whole-vacancy model.

## S5.5 — Requirement/skill semantic hardening

Re-enter #891 only after S0-S4 materially broaden evidence.

Sequence:

1. bounded requirement sections;
2. deterministic exact-span skills/languages/experience/certifications;
3. source/employer-held-out reviewed gold set;
4. optional Shadow ML/LLM candidate-span comparison for residual long tail;
5. deterministic promotion/provenance verification;
6. capability auto-fit;
7. numeric Fit;
8. Fit-dominant Combined calibration.

No employer vocabulary branch and no model-generated source truth.

## S6 — Cross-family Freeze-II acceptance

Target operator cohort:

- the expanded post-sensor candidate cohort is explicitly frozen with initial-67 + added-candidate delta accounting;
- generic connector-generation success is reported against the full frozen cohort, with ~95% as the strong engineering target;
- connector-smoke completeness = **100% of the frozen cohort**;
- every frozen-cohort candidate has a recorded live-search outcome, including explicit zero-yield where appropriate;
- >=10 unseen/current real vacancies;
- >=5 distinct source/ATS families;
- includes real proven jobs from the broadened S1 fleet;
- exact source reconcilable from Product;
- known false-confident critical metadata = 0;
- supported projection loss = 0;
- unknown/conflict remains explicit;
- CR-F1-001 completes at least once end-to-end without manual DB repair.

## Current sequence

`S0 COMPLETE -> S0.5 LinkedIn/Indeed conservative sensors -> S0.6 new candidate expansion -> freeze expanded candidate cohort -> S1 generic connector creation (~95% strong target, 100% eventual smoke) -> systematic live search -> S2 source-family understanding in parallel -> S3/S4 metadata extraction/integrity -> S5 optional ML shadow pilot -> S5.5 skill semantics -> S6 acceptance`

The residual classifier remains an **implementation-ordering instrument**, not a scope limiter. Common source-family mechanics should be solved first for leverage, but the long tail stays in the denominator.

## Immediate next gate

1. implement and qualify conservative LinkedIn + Indeed sensor plans using an approved search-provider/API transport only;
2. run a bounded real sensor proof with explicit request/budget accounting;
3. feed the resulting minimal company signals through known-candidate suppression and bounded candidate expansion;
4. freeze the expanded candidate cohort;
5. start the generic connector-builder campaign against the whole frozen cohort, reporting ~95% generic-generation success as a strong target and 100% eventual smoke coverage;
6. only after the live connector sweep broadens real vacancy evidence, re-enter metadata/extraction hardening and assess ML-data sufficiency.
