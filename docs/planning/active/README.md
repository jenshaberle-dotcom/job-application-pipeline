# Active Planning

Status: current planning truth  
Active product track: **PRODUCT-RECOVERY-001 / issue #783**  
Retained deterministic track: **ACQ-GENERALIZATION-90 / issue #676**  
Current release checkpoint: **`v0.1.0-demo.1`**

## Product authority

The Pipeline is a **Class A — Intent Locked** project.

Active engineering planning is subordinate to the operator-approved product contract under `docs/reference/product-contract/`.

Current planning must not infer product behavior from code, historical branches or demo pressure.

## Current steering rule

**PRODUCT-RECOVERY-001 / issue #783 is the current sequencing authority.**

Read first:

1. `product_recovery_001.md` — active recovery plan and milestones;
2. `../../current/product.md` — current product checkpoint and recovery objective;
3. `../../current/architecture.md` — current architecture/integration debt;
4. `../../current/pipeline.md` — source + concrete-job state machines;
5. `../../reference/product-contract/PRODUCT_DECISION_REGISTER.md` — approved/open product semantics.

DEMO-001 is a salvaged checkpoint. ACQ-GENERALIZATION-90 remains preserved and resumable, but neither is allowed to override the current Product Recovery sequence.

## Primary product metric

The current target is not connector-count, test-count or raw `rankable` count.

Primary acceptance metric:

> **At least five current Employer-Origin vacancies that pass all approved evidence/hard-filter gates and the approved recommendation threshold (currently 70/100), produced through one normal observable cold-to-application flow; plus a review-ready application package requiring only small edits.**

The result is allowed to contain fewer than five recommendations when fewer than five jobs meet the product contract. Engineering must improve coverage/quality rather than lower the threshold to fill the list.

## Current baseline

Repository checkpoint:

- DEMO-001 salvage merged by PR #781;
- release checkpoint `v0.1.0-demo.1`;
- Release Management established through REL-001/REL-002 and subsequent release requests.

Local operator evidence from 2026-09-03 (non-portable runtime proof):

- 30 bounded candidates inspected;
- 28 live vacancies observed;
- 7 live role/Candidate-Fact matches;
- 6 stale assessment snapshots refreshed;
- 6 jobs became rankable after evidence-backed review;
- only one of the six met the approved 70/100 recommendation threshold;
- provider-backed application generation and four-file+ZIP packaging worked technically;
- application content/layout still required product-quality iteration.

This baseline demonstrates **integration debt**: strong components exist, but normal product throughput and usability are not yet strong enough.

## Current sequence

### 1. M0 — baseline and complexity inventory

- map the authoritative surface at each product stage;
- classify demo/refill/recovery runners as retain/integrate/retire;
- establish cold-run baseline metrics and failure cohorts;
- surface any product-contract vs implementation drift.

### 2. M1 — Employer-Origin/currentness truth propagation

- keep discovery provenance separate from resolved Employer-Origin action URL;
- ensure Product read models use current Employer-Origin truth;
- filter known stale/closed vacancies before recommendation/application;
- preserve historical observations as lineage only.

### 3. M2 — single normal orchestration

- connect discovery -> origin -> currentness -> ingest -> assessment -> hard filter -> ranking;
- replace healthy-operation dependence on scout/integrity/refill/evidence-close choreography;
- expose stage status and exact stop reason.

### 4. M3 — recommendation throughput

- increase evidence-complete rankable population through normal execution;
- improve relevant Employer-Origin coverage;
- close avoidable hard-filter evidence gaps;
- reach >=5 jobs meeting the approved recommendation threshold without product-policy override.

### 5. M4 — application quality

- preserve/rebuild coherent CV layout;
- improve vacancy-specific content grounded in Candidate Facts/exact job evidence;
- visually validate DOCX/PDF;
- retain ZIP convenience and review-only/no-submit boundary.

### 6. M5 — harvest and release

- retire redundant demo/recovery wrappers after replacement proof;
- consolidate overlapping views/policies where safe;
- update current/reference docs;
- publish the next product checkpoint via GitHub Release Management.

See `product_recovery_001.md` for detailed exit criteria.

## Hard product boundaries during recovery

- Aggregator discovery alone is never final Top-5/Application authority.
- Known stale/closed jobs cannot remain current/recommended.
- `rankable` does not mean `recommended`.
- Top 5 remains at most five and current minimum overall quality remains 70/100 unless explicitly changed by the operator.
- Missing required evidence stays review-required/blocked.
- Provider output is not ranking/application approval authority.
- Application output remains `draft_for_review`; no automatic submission/send.
- CI does not prove local DB/provider/live employer truth.

## Retained DEMO-001 tooling

The following helpers are retained as diagnostic/recovery evidence, not steady-state architecture:

- `scripts/run_demo_001_local_server.py`
- `scripts/run_demo_001_operator_smoke.py`
- `scripts/run_demo_001_rankable_refill_scout.py`
- `scripts/run_demo_001_rankable_refill_integrity.py`
- `scripts/run_demo_001_rankable_refill_campaign.py`
- `scripts/run_demo_001_hard_filter_evidence_close.py`
- `scripts/run_product_v1_top5_policy_review.py`

Harvest their useful checks/authority bindings into the normal path before retiring wrappers.

## Preserved deterministic continuation — ACQ-GENERALIZATION-90 / #676

ACQ-GENERALIZATION-90 remains valid retained work and evidence, but is **not current sequencing authority**.

Retained anchors:

- `acq_generalization_90_reentry.md`;
- `acq_generalization_90_reentry.json`;
- `acq_generalization_90_target.md`;
- `acq676_external_deterministic_salvage.md`;
- `deterministic_connector_builder_layers.md`.

Historical metric remains `36/65` strict deterministic acquisition until a newly materialized unchanged strict E2E proof establishes a higher numerator.

Resume #676 as an independent track only after explicit reprioritization, or reuse its generic deterministic capabilities when they directly support Product Recovery M1–M3.

## Deferred/retained tracks

- `APP-TRACK-001 / #737` — post-application lifecycle retained, no expansion before core recovery.
- LLM acquisition booster — retained behind evidence-backed deterministic/current product needs.
- ML algorithm path — foundation may remain, productive expansion deferred until stable Product Recovery data/feedback surface exists.
- broad cloud/Kafka/Spark work — deferred without direct product-value justification.
- further demo-only orchestration — rejected as a substitute for normal product flow.

## Release discipline

Product-visible checkpoints must be published through the canonical GitHub Release process.

A release should document:

- visible features/outcomes;
- bug fixes;
- product metric/proof changes;
- known limitations;
- safety/authority boundaries;
- local operator evidence only when explicitly labeled as non-portable runtime proof.

Release tags are immutable product checkpoints. Commit history alone is not the operator-facing change history.

## Workspace discipline

Every mutating slice:

- starts from fresh remote `main`;
- uses the declared project worktree root under `$HOME/worktrees/job-application-pipeline`;
- does not branch from historical feature-branch ancestry;
- verifies exact head/CI before merge;
- reconciles re-entry/current docs when sequencing changes.

## Truth rules

- Operator-approved PRD/PD/PA surfaces define desired behavior.
- Repository code/tests/migrations define implementation truth.
- DB/runtime/live bounded evidence is required for runtime claims.
- Releases document checkpoints but do not replace current product authority.
- Chat/assistant memory is not project truth.
- Missing evidence yields inspection/blocked state, not guessed success.
- Historical planning remains evidence, not current sequencing authority.
