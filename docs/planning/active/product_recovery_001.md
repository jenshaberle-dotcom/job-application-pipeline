# PRODUCT-RECOVERY-001 — Cold-to-Application Product Recovery

Status: **active product continuation**  
Owner issue: **#783**  
Started: 2026-09-03  
Predecessor checkpoint: **DEMO-001 / v0.1.0-demo.1**

## Why this track exists

DEMO-001 proved that many individual components are mature, but it also showed that the integrated product requires too much repair/operator intervention to deliver a small set of current useful jobs and a high-quality application package.

The recovery track changes the optimization target from subsystem completion/hardening to repeatable end-user product value.

## Primary product truth

A normal cold operator run must be able to produce:

```text
market discovery
-> Employer-Origin resolution
-> fresh exact vacancy proof
-> Bronze
-> Silver
-> current assessment
-> capability fit
-> hard filters
-> deterministic ranking
-> up to five recommendations satisfying the approved product threshold
-> Application Workspace
-> coherent CV/letter DOCX/PDF/ZIP draft_for_review
```

## Primary acceptance metric

The target is **not** simply `RANKABLE >= 5`.

The primary acceptance metric is:

> **At least five current Employer-Origin vacancies that pass all approved hard/evidence gates and the approved recommendation threshold (currently 70/100), produced through one normal observable product flow; plus an application package for a selected job that requires only small human edits.**

If fewer than five jobs genuinely meet the approved threshold, the truthful product output is fewer than five. Recovery work must improve discovery, evidence and job quality/throughput rather than weaken the threshold.

## Baseline from DEMO-001

Repository checkpoint:

- DEMO-001 salvage merged to `main` via PR #781;
- first release checkpoint: `v0.1.0-demo.1`;
- release notes preserve bug fixes, known limitations and local operator proof.

Local operator evidence on 2026-09-03 (non-portable runtime proof):

- 30 bounded candidates inspected;
- 28 live vacancies observed;
- 7 live role/Candidate-Fact matches;
- 6 selected assessments refreshed after detail drift;
- 6 jobs became `rankable` after capability/hard-filter evidence closure;
- only one of those six met the currently approved 70/100 recommendation threshold;
- provider-backed application generation and local DOCX/PDF/ZIP packaging worked technically;
- document content/layout still required further product-quality work.

This baseline is not a target state. It is the evidence explaining why recovery is necessary.

## Recovery principles

1. **No fake fill.** Never create demo-only rows, fake freshness, synthetic Product authority or below-threshold Top-5 fill.
2. **Origin before action.** Aggregators discover; Employer-Origin confirms action/recommendation authority.
3. **Freshness before ranking.** A known stale/closed vacancy cannot remain current/recommended.
4. **Current evidence before reuse.** Detail drift invalidates stale assessment/ranking evidence and triggers an audited refresh.
5. **One normal path.** Repair/refill helpers are temporary recovery tools, not the desired operator experience.
6. **Product quality over subsystem count.** Work must move the cold-to-application metric or be justified safety/reliability maintenance.
7. **Release visible progress.** Product checkpoints are released with explicit features, bug fixes, limitations and operator proof.

## Milestones

### M0 — Recovery baseline and complexity inventory

Goal: establish one authoritative map of the current product-value path and all parallel/recovery surfaces.

Tasks:

- map every stage from discovery through application;
- identify the authoritative table/view/module/runner per stage;
- classify duplicate/overlapping views, policies, scripts and repair paths;
- separate normal product orchestration from diagnostic/recovery helpers;
- record current baseline metrics and failure cohorts;
- identify product-contract drift before changing behavior.

Exit criteria:

- one reviewed architecture/pipeline map;
- one current baseline report;
- every major repair helper has `retain / integrate / retire` disposition.

### M1 — Employer-Origin + currentness truth propagation

Goal: no discovery/aggregator truth leaks into Product/Application authority.

Tasks:

- keep discovery provenance separate from resolved Employer-Origin vacancy URL;
- project resolved origin/currentness consistently into Product read models;
- remove ambiguous fallback action URLs;
- establish bounded live revalidation before recommendation/application;
- ensure stale/closed jobs fall out of current/actionable/recommended views while historical lineage remains preserved.

Exit criteria:

- zero BA/StepStone/GuteJobs final action URLs in the recommendation/application path;
- known stale/closed jobs cannot survive the currentness gate;
- Product UI explains discovery origin vs action origin.

### M2 — Single cold Product V1 orchestration

Goal: replace demo repair choreography with one normal observable flow.

Tasks:

- orchestrate discovery -> origin -> ingest -> currentness -> assessment -> capability -> hard filter -> ranking;
- make each stage idempotent/bounded where required;
- expose stage status and stop reason;
- reuse existing canonical modules instead of copying demo logic;
- keep manual/operator gates only where product contract genuinely requires them.

Exit criteria:

- one documented operator command/action;
- no manual scout/integrity/refill/evidence-close sequence required during healthy operation;
- failure stops identify exact stage and next safe action.

### M3 — Recommendation throughput and quality

Goal: normal operation yields enough high-quality jobs without lowering product gates.

Tasks:

- measure why jobs stop before rankable;
- reduce avoidable evidence gaps;
- improve capability/hard-filter evidence extraction;
- increase Employer-Origin coverage for relevant roles;
- keep PD-050/PD-051 semantics unchanged unless the operator explicitly changes them;
- add product-value E2E regression around five threshold-qualified recommendations when the controlled fixture/market cohort contains them.

Exit criteria:

- at least five freshly verified Employer-Origin jobs meet all approved gates and score >=70 in the acceptance campaign;
- no threshold override or quota fill used;
- ranking explanations/uncertainty visible.

### M4 — Application quality

Goal: generated documents are genuinely useful, not only technically valid.

Tasks:

- preserve or deliberately reconstruct coherent CV structure;
- adapt content to exact vacancy while preserving Candidate Facts truth;
- improve letter specificity and remove structural duplication;
- validate DOCX and PDF visually, not only via text extraction;
- keep provider/fallback behavior bounded and explicit;
- retain one-click ZIP package.

Exit criteria:

- CV and letter open correctly in Word/PDF viewers;
- content is vacancy-specific and evidence-grounded;
- no compiler/debug markers or duplicated envelope/greeting/closing;
- operator judges both documents to require only small edits before sending.

### M5 — Complexity harvest and product release

Goal: remove temporary complexity after the normal path is proven.

Tasks:

- retire or archive demo-only/recovery runners replaced by normal orchestration;
- collapse overlapping policies/read models where safe;
- update current/reference/planning docs;
- add/adjust E2E product-value CI;
- publish the next GitHub Release with explicit changes and remaining limits.

Exit criteria:

- one clear normal product path;
- retained recovery tooling has explicit purpose;
- documentation/re-entry/release notes agree;
- next release published from canonical `main`.

## Current retained demo/recovery helpers

The following are evidence/recovery tools, not desired steady-state orchestration:

- `run_demo_001_local_server.py`
- `run_demo_001_operator_smoke.py`
- `run_demo_001_rankable_refill_scout.py`
- `run_demo_001_rankable_refill_integrity.py`
- `run_demo_001_rankable_refill_campaign.py`
- `run_demo_001_hard_filter_evidence_close.py`
- `run_product_v1_top5_policy_review.py`

They must be harvested deliberately: preserve useful validation/authority logic, integrate it into normal orchestration where appropriate, then retire redundant wrapper choreography.

## Product-contract anchors

- `docs/reference/product-contract/PRD.md`
- `docs/reference/product-contract/PRODUCT_DECISION_REGISTER.md`
- `docs/reference/product-contract/ACCEPTANCE_SCENARIOS.md`
- `docs/reference/product-contract/TRACEABILITY.md`

Key current decisions include:

- PD-043 — Employer-Origin confirmation for Top-5;
- PD-050 — Top 5 means at most five;
- PD-051 — minimum overall quality 70/100;
- PD-053/054 — hard-filter/required-evidence gating;
- PD-071 — no automatic application submission;
- PD-075 — explicit application provider trigger/context boundary (once rebaseline merged);
- PD-080 — minimum end-to-end Product V1 journey (once rebaseline merged).

## Retained tracks

### ACQ-GENERALIZATION-90 / #676

Preserved and resumable, but not current sequencing authority. Its deterministic acquisition evidence can be reused when it directly advances M1/M2/M3.

### ML foundation

Preserved but no productive ML expansion until the deterministic/current Product Recovery path is stable and provides a suitable training/feedback surface.

### APP-TRACK-001 / #737

Preserved as post-application backlog. Do not expand it ahead of the core cold-to-application recovery.

## Release discipline

Each material Product Recovery checkpoint should be published through GitHub Release Management.

Release notes must answer:

- What product behavior became more reliable/useful?
- Which user-visible bugs were fixed?
- What exact product metric/proof improved?
- Which limitations remain?
- Which local runtime facts were operator-validated but are not repository state?

## Definition of done

PRODUCT-RECOVERY-001 is done only when:

- one normal cold-to-application flow exists and is documented;
- current Employer-Origin truth propagates end to end;
- stale/aggregator-only jobs do not become recommendations/actions;
- an acceptance campaign yields >=5 jobs meeting the approved recommendation contract without overrides;
- Application Workspace produces near-submission-quality review documents;
- normal CI plus product-value E2E proof protects the path;
- redundant demo/recovery complexity is harvested;
- current docs/re-entry and GitHub Release history are reconciled.
