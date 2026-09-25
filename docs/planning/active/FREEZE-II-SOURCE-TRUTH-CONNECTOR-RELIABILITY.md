# Freeze II — Source Truth & Connector Reliability

Status: ACTIVE — S0 COMPLETE; S1 connector saturation active
Canonical issue: #1038
Previous campaign: F0-F6 COMPLETE / OPERATOR ACCEPTED FOR CURRENT COHORT

## Mission

The next JAP freeze campaign deliberately moves upstream.

Primary loop:

`all current candidates connector-bound -> isolated smoke proof -> systematic real search -> broad current job evidence -> metadata extraction hardening -> more trustworthy JAP Control Center`

The campaign does not begin by adding ranking, Fit, UI or application features. The present learning bottleneck is source breadth. The first objective is therefore connector saturation across the complete current Employer-Origin candidate population, followed by systematic real search. Metadata extraction becomes the primary hardening wave only after that broader real-job population exists.

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
2. **Connector operability and Product source coverage are separate metrics.** Every current candidate is expected to have an executable connector binding and smoke proof; Product coverage still changes only after real materialized strict genuine-job E2E proof.
3. A connector smoke may emit exactly one synthetic/non-authoritative job envelope, but smoke data is persistence-forbidden and may never enter Bronze, Silver, Gold/Product, ranking or application state.
4. Every current candidate must receive a systematic real source-search attempt. A valid outcome is `real jobs observed`, `real zero-yield`, or `blocked with explicit reason`; silent skipping is forbidden.
5. Existing candidacy is sufficient justification for connector/search engineering because each candidate originated from prior relevant-employer/job evidence. It is not current vacancy authority.
6. Source identity, reachability, inventory completeness, query/search behavior, detail identity and field extraction are separate dimensions.
7. Missing/conflicting metadata remains explicit unknown/conflict.
8. Bronze preserves evidence; Silver owns canonical normalized field truth; Product/CC may not manufacture stronger downstream truth.
9. Employer-specific exceptions are forbidden unless generalized into reusable source/template-family contracts or candidate bindings over a shared engine.
10. Deterministic structured or bounded visible evidence is first lane. ML/LLM may later propose Shadow evidence only; neither creates source truth.
11. Fit/Combined/ranking authority does not expand until upstream gates pass.

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

## S1 — Connector saturation across the complete candidate population — ACTIVE

Primary work: #789 + CR-F1-001 + current 67-candidate S0 denominator.

The primary S1 metric is no longer "a few additional connectors". It is **candidate connector saturation**.

### S1A — 100% connector binding + isolated smoke

For every current distinct Employer-Origin candidate:

- derive the canonical binding `generic_origin:<company_key>`;
- prove the default registry resolves it to the Employer-Origin connector family;
- execute a connector-contract smoke that emits one synthetic dummy `RawJobRecord`;
- mark the smoke evidence explicitly non-authoritative and persistence-forbidden;
- never pass the synthetic record to Bronze/Silver/Product.

Initial denominator: **67/67** from S0. Future candidates automatically extend the denominator.

### S1B — 100% real source execution attempt

For every candidate, execute the real source path independently of whether a relevant job is currently open.

Each candidate must end in exactly one explicit state:

- `real_jobs_observed`;
- `real_zero_yield`;
- `origin_resolution_required`;
- `source_unreachable`;
- `inventory_or_detail_blocked`;
- `proof_blocked`.

No candidate may disappear because a strict Product gate has not yet passed. Product activation remains separate.

### S1C — systematic relevant-job search

Once a candidate has a usable real source path:

- search company-grounded vocabulary first;
- fill remaining breadth from the canonical target raster;
- use impossible/control-query discrimination where the source supports query semantics;
- collect real current job/detail evidence read-only first;
- retain truthful zero-yield when no current relevant vacancy exists;
- only real Employer-Origin evidence may later enter normal Bronze/Silver ingestion.

S1 acceptance:

- **100% current candidates connector-smoke PASS**;
- **100% current candidates real-search attempted or explicit source blocker**;
- zero silent skips;
- every source/search outcome has bounded request accounting;
- real jobs are attributable to exact source/detail evidence;
- no synthetic smoke data persisted;
- reusable mechanics are shared across candidates instead of employer-name code branches.

The currently running residual classifier is supporting evidence only. It helps implement shared mechanics, but it does not narrow S1 to a small "high-lift" subset and no longer owns sequencing.

The #676 >=90% strict Product-coverage target remains a separate long-term measure. Connector saturation can reach 100% before strict Product coverage does; the two numbers must never be conflated.

## S2 — Source/search evidence breadth + source-family capability matrix

After S1 has exercised the complete candidate population, build the source/search evidence matrix from those real executions. For every material source/ATS family record:

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

## S5 — Requirement/skill semantic hardening

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

- >=10 unseen/current real vacancies;
- >=5 distinct source/ATS families;
- includes newly activated S1 connectors;
- exact source reconcilable from Product;
- known false-confident critical metadata = 0;
- supported projection loss = 0;
- unknown/conflict remains explicit;
- CR-F1-001 completes at least once end-to-end without manual DB repair.

## Current sequence

`S0 COMPLETE -> S1 connector saturation (all candidates) -> S2 systematic real-search/source-family matrix -> S3 metadata extraction -> S4 integrity -> S5 semantics -> S6 acceptance`

S1 is denominator-driven, not cohort-driven: every current candidate participates. Residual classification remains useful only to decide which shared capability fixes unblock many candidates at once. S2 consumes the resulting full-population real-search evidence. S3 metadata hardening starts only after that breadth exists.

## Immediate next gate

Install and qualify the S1 connector-saturation harness against the complete current candidate population. First prove 100% canonical connector binding plus isolated synthetic smoke without persistence. Then execute bounded real-source/systematic-search passes across all candidates in batches until every candidate has either real job/zero-yield evidence or an explicit source blocker. Use residual diagnostics only to repair shared mechanics. Do not wait for metadata hardening before broadening the source population.
