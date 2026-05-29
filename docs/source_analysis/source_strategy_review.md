# Source Strategy Review — S2

## Purpose

S2 starts after the first controlled source-coverage expansion target was activated: `greenhouse:contentful`.

The purpose of this review is to avoid continuing source expansion by habit. The project has already learned that more source targets and more raw rows do not automatically create more value.

S2 therefore asks which source family or source target should be expanded next for the user's actual search context:

```text
Hannover region or remote in Germany
```

The review must compare source value, acquisition risk, operational effort and explainability before adding more Greenhouse, Personio, employer-origin or aggregator targets.

## Why S2 Exists Now

S1 deliberately stopped after one controlled Greenhouse addition.

The active system now includes:

- a stable German public API baseline through Bundesagentur
- Greenhouse ATS boards with Stripe and Contentful
- selected Personio / employer-near ATS targets
- a defensively limited StepStone aggregator signal

This is enough to start evaluating source strategy without immediately adding another board.

Known interpretation caveats still apply:

- `greenhouse:stripe` contains historical burden and must not be treated as clean market volume
- Bundesagentur has a first-source time advantage and strong regional Silver evidence
- StepStone intentionally fetches only one full result page and is not a full-market crawl
- Personio targets are employer-near but currently low volume
- `greenhouse:contentful` is a new coverage change and needs scheduled observation before long-term value claims

## Primary Question

The primary S2 question is:

```text
Which next source move creates unique, explainable value for Hannover or remote-in-Germany job search intelligence?
```

A source move can be valuable even when it does not immediately become a production ingestion connector. For example, an aggregator may be useful as a discovery source for employers, titles or vocabulary gaps, while still being unsuitable as a broad automated ingestion source.

## Source Families Under Review

| Source family | Current role | S2 review question |
|---|---|---|
| Bundesagentur | Official API and regional baseline. | Keep as benchmark; use to compare whether other sources add unique value. |
| Greenhouse | Employer-near ATS boards. | Does another board add German/remote relevance, or mostly duplicate low-value coverage? |
| Personio | Employer-near European ATS targets. | Which targets add unique employer-origin evidence rather than low-volume noise? |
| StepStone | Limited commercial aggregator signal. | Can it support discovery without broader crawling or higher operational risk? |
| Employer-origin sites | Potential canonical employer evidence. | Which known employers are worth targeted validation before connector work? |
| Aggregators | Potential discovery family. | Can LinkedIn, XING, Indeed or Glassdoor help discover relevant employers, titles and vocabulary without becoming uncontrolled scraping targets? |

## Aggregator Boundary

S2 treats commercial aggregators as a separate source family.

They should not automatically be modeled as canonical job sources. Their first possible role is discovery:

- discover relevant employers in Hannover or remote Germany
- discover alternative titles and vocabulary not covered by current search terms
- identify employer-origin boards worth validating
- compare whether BA, StepStone, Greenhouse and Personio miss important signals
- support false-negative analysis without committing to broad ingestion

Possible aggregator roles:

| Role | Meaning | Default stance |
|---|---|---|
| `discovery_source` | Used manually or semi-automatically to discover employers, titles or source targets. | Preferred first role. |
| `market_signal_sampler` | Used in a bounded way to understand market vocabulary or coverage gaps. | Possible after analysis. |
| `direct_ingestion_source` | Used as an automated Bronze ingestion source. | High bar; not assumed. |
| `canonical_source` | Treated as authoritative employer evidence. | Not preferred when employer-origin or ATS source exists. |

Aggregators must not be expanded into uncontrolled crawling. If they are evaluated technically, the evaluation should be defensive, bounded and documented before implementation.

## Candidate Groups To Reassess

S2 should reassess, not rediscover, the known candidate groups.

### Greenhouse / ATS boards

Carry forward:

- `greenhouse:commercetools` as validation evidence only
- `greenhouse:celonis` as reserve evidence only
- selected Personio targets only when employer relevance is clear

Do not add another Greenhouse board only because the connector already exists.

### Employer-origin candidates

Carry forward known employer-origin candidates from the selection matrix:

- HDI
- ROSSMANN
- Finanz Informatik
- WERTGARANTIE

These candidates should be reviewed for target quality, vocabulary fit and Hannover/remote relevance before implementation.

### Aggregator candidates

Evaluate aggregators as a family first:

- LinkedIn
- XING
- Indeed
- Glassdoor

The first question is not whether they can be scraped. The first question is whether they can responsibly and usefully improve discovery, source-target selection or false-negative analysis.

## Decision Gates

Before adding another active source target, S2 should answer:

1. Does the source improve Hannover or remote-in-Germany relevance?
2. Does it add unique companies, roles or vocabulary compared with BA, StepStone, Greenhouse and Personio?
3. Can the source be acquired defensively with bounded requests and transparent lineage?
4. Is the source better used as direct ingestion, discovery-only or manual review input?
5. Can the result be explained in source-value snapshots and future Gold views?
6. Does the expected value justify maintenance effort and operational risk?

## Allowed Outcomes

S2 may conclude any of the following:

- activate one additional validated company or ATS target
- keep Greenhouse expansion paused
- keep Personio expansion paused until a better target is identified
- treat aggregators as discovery-only for now
- build a small aggregator analysis spike before any ingestion decision
- prioritize employer-origin validation over more ATS boards
- update search terms before adding new sources

A decision to not build a connector can be a valid engineering outcome.

## Non-Goals

S2 does not implement broad ingestion from LinkedIn, XING, Indeed or Glassdoor.

S2 does not authorize large-scale Greenhouse or Personio expansion.

S2 does not redefine Bronze as strict pre-filtered storage. Bronze remains tolerant and raw-first.

S2 does not promote aggregator results into canonical source evidence without employer-origin or ATS validation.

## Next Implementation Shape

Recommended next small implementation block after this boundary document:

```text
S2B — Aggregator / discovery source family assessment
```

S2B has been documented in `docs/source_analysis/aggregator_discovery_assessment.md`.

Its current conclusion is that LinkedIn, XING, Indeed and Glassdoor should be treated as discovery sources first, not as direct automated Bronze ingestion sources. Aggregators may help discover employers, role vocabulary and false-negative candidates, but persistent ingestion should still prefer employer-origin or ATS-near sources when possible.

S2C has been documented in `docs/source_analysis/aggregator_discovery_feasibility_matrix.md`.

It adds hard gates before any aggregator can become an automated probe or connector. Legal / terms risk is treated as a blocker, not as a soft implementation concern. A technically possible acquisition path is rejected when it relies on unclear scraping, login automation, browser automation, non-official third-party data or storage rights that do not fit the project.

S2E has been documented in `docs/source_analysis/employer_candidate_false_negative_review.md`.

It quantifies employer-candidate visibility and false-negative risk before another active source target is selected. The goal is not to prove that missing employers have no jobs. The goal is to detect whether the current pipeline misses expected market candidates because of source coverage, search terms, fetch limits or Silver relevance filters.

S2F has been documented in `docs/source_analysis/employer_origin_source_candidate_review.md`.

It validates a small set of employer-origin / ATS-near candidate paths with one bounded request per employer target. S2F is not a connector and does not make source activation automatic. It exists to decide whether a candidate is worth manual review before controlled source-target activation.

S2G has been documented in `docs/source_analysis/active_source_target_decision_after_s2f.md`.

It selects Finanz Informatik as the next manual source-target validation candidate after S2F. This is not a connector decision yet. It is a controlled decision to inspect one promising employer-origin path before any implementation.

S2H has been documented in `docs/source_analysis/finanz_informatik_origin_path_review.md`.

It confirms that the Finanz Informatik origin path appears technically viable enough for a later bounded source-target spike. The main finding is not duplicate noise, but relevance and scope control. Any future spike must apply strict relevance gates before ingestion, especially for training, dual-study, working-student, trainee and non-target-location roles.

S2I has been documented in `docs/source_analysis/finanz_informatik_bounded_source_target_spike_design.md`.

It defines the Finanz Informatik spike as read-only, export-first and relevance-gated. The design explicitly prevents broad all-job ingestion and requires URL gates, exclusion gates, request boundaries and stop conditions before any connector or Bronze persistence decision.

S2J was an early Finanz Informatik source-target spike. In S2O-A1, its active script path was retired because the project now uses bounded connector-candidate preview logic instead of local handoff artifacts.

### S2K — Finanz Informatik Detail-Page Probe

S2K was an early tiny detail-page probe. In S2O-A1, its active script path was retired because S2L/S2N now use live connector-candidate preview data and current database evidence.

### S2L — Finanz Informatik Incremental Uniqueness Review

S2L has been documented in `docs/source_analysis/finanz_informatik_incremental_uniqueness_review.md`.

It evaluates Finanz Informatik as a precision source instead of a broad-volume source. The review checks whether the selected S2K candidates add incremental value compared with existing raw and Silver evidence.

The key question is not whether Finanz Informatik produces many jobs. The key question is whether it produces relevant, non-duplicate jobs that are not already visible from BA or other sources.


### S2M Preparation — Finanz Informatik Connector Candidate

S2M connector candidate has been documented in `docs/source_analysis/finanz_informatik_connector_candidate.md`.

A bounded connector candidate exists in `src/connectors/finanz_informatik.py`, but it is not activated by a search profile. It is intentionally limited to one listing page, at most three detail pages, target-scope candidates and relevance-gated RawJobRecord creation.

Activation remains deferred until incremental uniqueness and source value have been reviewed.


### S2N — Finanz Informatik Activation Gate Review

S2N has been documented in `docs/source_analysis/finanz_informatik_activation_gate.md`.

S2N is DB-backed and connector-preview-backed. It runs the bounded Finanz Informatik connector candidate, reuses the S2L incremental-uniqueness comparison logic against current database evidence and writes generated review artifacts only after the decision has been built from live evidence.

If database evidence is unavailable, S2N must fail instead of producing an activation decision.

This preserves the project rule that local exports are artifacts, not durable pipeline inputs, and avoids local-artifact handoffs that would create cloud or CI migration debt.


### S2O — Export-as-Input Refactoring Audit

S2O has been documented in `docs/source_analysis/export_as_input_refactoring_audit.md`.

It captures the remaining local export-as-input workflows that must be refactored before cloud migration or production-like operation. Generated files may remain useful as human-readable review artifacts, but they must not become hidden pipeline inputs, activation gates, destructive-operation inputs or migration dependencies.

Known follow-ups now focus on the historical-burden hot-store removal handoff and a regression guard against new export-as-input workflows. The legacy Finanz Informatik S2J/S2K local handoff has been retired in S2O-A1. S2L and S2N are already refactored to use live connector-candidate preview data and current database evidence instead of local export files.


### S2O-A1 — Finanz Informatik Legacy Spike Retirement

S2O-A1 has been documented in `docs/source_analysis/finanz_informatik_legacy_spikes_retirement.md`.

It removes the old Finanz Informatik S2J/S2K local handoff scripts from the active codebase. The project keeps the bounded-source lessons, but future Finanz Informatik decisions must use the connector-preview-backed and DB-backed S2L/S2N path.

This keeps local review artifacts out of activation and persistence decisions and avoids carrying obsolete handoff logic into cloud/CI work.


### S2O-B — Historical Burden DB-Backed Review State

S2O-B has been documented in `docs/source_analysis/historical_burden_db_backed_review_state.md`.

Stage 1 introduces database-backed proposed review batches for historical-burden hot-store removal. The prepare step now reads current database evidence, persists proposed review state to `historical_burden_review_batches` and `historical_burden_review_items`, and writes Markdown/JSON only as human-readable review artifacts.

Stage 2 remains open: the guarded removal command must be refactored to read an approved DB batch by `batch_id` instead of local candidate/manifest files.


### S2O-B Stage 2 — DB-Backed Historical Burden Execution

The guarded historical-burden hot-store removal command now reads DB-backed review state by `batch_id`. It does not read local CSV or manifest files as execution input. Dry-run remains the default. Approval and execution require explicit command flags and exact confirmation strings.

This closes the historical-burden export-as-input blocker for the hot-store removal workflow. Generated Markdown/JSON files remain human-readable reports only.

### S2P — Finanz Informatik Controlled Activation and Scheduler Watchdog

S2P activates exactly one controlled Finanz Informatik source target: `finanz_informatik:hannover`. The activation is intentionally narrow and keeps the source in precision-source semantics: low volume is acceptable when the source adds relevant, non-duplicate employer-origin evidence.

S2P also documents a local Windows scheduler watchdog. The watchdog is local-development infrastructure only; it catches up after missed days by running at logon and skipping duplicate same-day runs through an operational state marker. It is not cloud orchestration and must be replaced before production/cloud operation.

## S2Q Employer-Origin Connector Build Process

S2Q defines the employer-origin connector build process in `docs/source_analysis/employer_origin_connector_build_process.md`.

The process uses the Finanz Informatik controlled activation as the reference path. It formalizes source discovery, risk gating, bounded previews, relevance filtering, detail evidence, incremental uniqueness, connector-candidate review, controlled activation, Bronze validation, Silver validation and lifecycle tracking.

This is intentionally defensive. A future AI agent should execute the process gate by gate and stop at the first failed hard gate. A documented stop is a valid outcome. Aggregators remain useful for employer discovery and market exploration, while employer-origin sources should provide controlled, high-precision source targets when the gates justify them.

## S2R Employer-Origin Candidate Gate-State Model

S2R adds a DB-backed gate-state model for employer-origin source candidates.

This follows the S2Q connector build process and prevents future scripts or agents from relying on CSV, Excel or generated review artifacts as hidden process inputs. Candidate state, gate decisions and stop reasons now have a PostgreSQL-backed target model that can later support agent-assisted connector candidate workflows.

## S2S Employer-Origin Gate Agent MVP

S2S introduces a bounded gate-agent MVP for employer-origin source candidates.

The agent uses the S2R DB-backed gate-state model and executes the first S2Q gates up to relevance. It performs a single bounded read-only request, records decisions in PostgreSQL and stops at the first failed or manual-review gate. It does not generate connector code, activate sources, write Bronze data or rely on CSV/Excel/export artifacts as inputs.

## S2T Employer-Origin Detail Evidence and Incremental Uniqueness Agent

S2T extends the employer-origin gate-agent workflow beyond early reachability and relevance gates.

It reads DB-backed candidate state, fetches a bounded set of detail pages, records detail evidence and compares candidates against current raw/Silver evidence. A candidate may move to `connector_candidate` only when incremental value is plausible. The agent still does not generate connector code, activate sources, write Bronze rows or use CSV/Excel/export artifacts as inputs.

## S2U Employer-Origin Connector Candidate Agent

S2U adds the connector-candidate gate agent.

The agent reads DB-backed gate state and only passes `connector_candidate_gate` when the earlier discovery, risk, reachability, scope, relevance, detail evidence and incremental uniqueness gates are passed. It writes the connector-candidate specification back to PostgreSQL gate evidence and may emit human-readable review outputs. It does not generate connector code, activate sources, write Bronze data or use CSV/Excel/export artifacts as inputs.

## S2V Employer-Origin Connector Implementation Agent

S2V materializes a passed DB-backed `connector_candidate_gate` into bounded repository files for a connector implementation candidate.

The agent reads PostgreSQL gate evidence and writes code, tests and documentation directly into the branch. This avoids CSV/Excel/export-as-input handoffs. The generated connector candidate is still inactive: registration, search-profile activation, Bronze persistence and recurring ingestion remain separate controlled gates.

## S2U/S2V Concrete Detail-URL Hardening

The employer-origin connector agents now treat overview pages, career roots and legal pages as invalid detail evidence. A candidate must provide concrete job-detail URLs before `connector_candidate_gate` may pass or connector code may be generated. This keeps the process defensive and prevents agent-generated connector candidates from being based on weak or non-job evidence.

## S2W Employer-Origin Detail Evidence Repair Agent

S2W adds a bounded self-correction step to the employer-origin agent chain. When a source candidate has weak detail evidence such as career overview pages, legal pages or generic job-board roots, the agent can perform a limited same-domain repair attempt, validate concrete job-detail URLs and update the PostgreSQL `detail_evidence_gate`.

The repair remains defensive: it does not activate sources, write Bronze rows, register connectors, use browser automation, persist raw HTML or use CSV/Excel/export artifacts as inputs.

## S2X Employer-Origin Agent Chain Driver

S2X introduces a conservative DB-backed orchestration layer for the employer-origin agent workflow. The chain driver reads PostgreSQL gate state, chooses exactly one next bounded step and then asks the user/operator to rerun it against refreshed DB state.

It can coordinate S2W detail-evidence repair, S2U connector-candidate gate evaluation and S2V connector implementation dry-runs without bypassing gates or using export artifacts as inputs.

## S2Y Employer-Origin Source Lifecycle Tracking

S2Y adds DB-backed lifecycle tracking for employer-origin sources and improves the agent-chain UX for controlled child exits. The lifecycle agent records `source_lifecycle_tracking` from current PostgreSQL evidence instead of leaving active controlled sources indefinitely at `not_started`.

The agent only updates gate state. It does not activate sources, write Bronze rows, transform Silver rows, enable recurring ingestion or use CSV/Excel/export artifacts as inputs.

## S2Z Employer-Origin Candidate Queue Agent

S2Z adds a DB-backed operator queue for employer-origin candidates. The queue agent reads current PostgreSQL gate state, classifies the next safe bounded action per candidate and prints actionable commands without executing them.

This keeps the workflow fast enough for repeated candidate work while preserving explicit operator control, gate discipline and the no CSV/Excel-as-input rule.

## S2Z Queue Safety Refinement

The candidate queue now treats fully completed `active_controlled` employer-origin sources as monitoring targets instead of implementation targets. This prevents the queue and chain driver from repeatedly suggesting connector implementation for sources whose gate model is already complete.

This is a safety and operator-UX refinement only. It does not activate sources, write Bronze rows, generate connector files or loosen any gate.

## S3A Repair Loop Safety

S3A prevents the employer-origin candidate queue from repeatedly proposing bounded detail-evidence repair after a candidate already stopped with `bounded repair found no concrete detail pages with profile and target/remote signals`.

This is intentionally conservative. A failed repair remains visible as a manual-review stop, but it is not offered as the next executable command again. This keeps the agent workflow productive and prevents hidden retry loops.
