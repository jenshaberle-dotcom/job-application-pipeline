# Freeze II — Source Truth & Connector Reliability

Status: ACTIVE — S0 baseline implementation / qualification
Canonical issue: #1038
Previous campaign: F0-F6 COMPLETE / OPERATOR ACCEPTED FOR CURRENT COHORT

## Mission

The next JAP freeze campaign deliberately moves upstream.

Primary loop:

`more Employer-Origin coverage -> better source understanding -> harder deterministic extraction -> less layer loss -> more trustworthy metadata in JAP Control Center`

The campaign does not begin by adding ranking, Fit, UI or application features. The present learning bottleneck is the breadth and reliability of source evidence reaching Bronze, Silver and Product.

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
2. Connector coverage changes only after materialized strict genuine-job E2E proof.
3. Source identity, reachability, inventory completeness, detail identity and field extraction are separate dimensions.
4. Missing/conflicting metadata remains explicit unknown/conflict.
5. Bronze preserves evidence; Silver owns canonical normalized field truth; Product/CC may not manufacture stronger downstream truth.
6. Field provenance must survive to the operator surface.
7. Employer-specific exceptions are forbidden unless generalized into reusable source/template-family contracts.
8. Deterministic structured or bounded visible evidence is first lane.
9. ML/LLM may later propose Shadow evidence only; neither creates source truth.
10. Fit/Combined/ranking authority does not expand until upstream gates pass.

## S0 — Current truth baseline + layer-loss map — ACTIVE

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

S0 boundary:

- DB writes 0;
- source activation 0;
- connector registration 0;
- Bronze/Silver/Product writes 0;
- provider/LLM calls 0;
- Fit/ranking/application authority 0.

## S1 — Connector breadth + fresh-company closure

Primary work: #789 + CR-F1-001.

Target:

- at least five newly strict-proven active Employer-Origin connectors;
- at least three distinct source/ATS families;
- activation only after strict proof;
- normal Bronze/Silver ingestion, no demo-only wiring;
- lift attributed to reusable technical classes, never employer-name branches.

The #676 >=90% target remains a useful long-term target. S0 must establish the current denominator before any new percentage is authoritative.

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

`S0 baseline -> S1 breadth -> S2 matrix -> S3 extraction -> S4 integrity -> S5 semantics -> S6 acceptance`

S1/S2 may overlap after S0. S3 may begin against high-lift reusable gaps exposed by S0/S2. S5 remains blocked until S0-S4 evidence is materially stronger.

## Immediate operator gate

Qualify and merge the S0 harness, then run the read-only S0 workflow on exact current `main`. Use that report to choose the first connector/source-family cohort by expected reusable lift and metadata risk. Do not activate or mutate any source during S0.
