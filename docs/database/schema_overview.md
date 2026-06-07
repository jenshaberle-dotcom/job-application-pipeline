# Database Schema Overview

Status: current schema reference
Scope: DOC-001H domain-level PostgreSQL map

## Purpose

This document gives a reader the database map that the architecture diagrams do
not show in detail.

It is intentionally organized by product responsibility instead of raw migration
order. The migration chain remains the source of truth for exact DDL, while this
page explains which table families belong together and why they exist.

## Schema domains

| Domain | Main objects | Product responsibility |
|---|---|---|
| Ingestion Core | `search_profiles`, `search_terms`, `ingestion_runs`, `raw_jobs`, `schema_migrations` | Run bounded source ingestion with reproducible profile/term lineage. |
| Observation & Source Value | `job_observations`, `source_value_snapshots`, `source_heartbeat`, `dashboard_*` views | Track repeated sightings, source behavior, health and relevance yield. |
| Silver & Canonical Jobs | `silver_processing_decisions`, `silver_jobs`, `job_lifecycle` | Normalize raw records and expose current job lifecycle state. |
| Historical Burden | `historical_burden_review_batches`, `historical_burden_review_items` | Separate old/noisy raw data from current hot-path value decisions. |
| Employer-Origin Candidates | `employer_origin_source_candidates`, `candidate_profiles`, `candidate_skills`, `market_evidence` | Model potential employer-origin sources before connector work. |
| Gate & Lifecycle Control | `employer_origin_candidate_gate_reviews`, `employer_origin_candidate_gate_events`, `candidate_reassessment_queue`, `candidate_market_evidence_summary` | Decide whether candidates can progress, must stop, or need repair/review. |
| Evidence & URL Discovery | `employer_origin_source_discovery_reviews`, `employer_origin_url_repair_reviews`, `candidate_origin_url_persistence_reviews`, `employer_origin_job_detail_evidence` | Discover, repair, persist and validate origin/detail URLs under gates. |
| Connector Build Governance | `employer_origin_connector_generation_plans`, `employer_origin_connector_build_requests`, `connector_feasibility_reviews`, `connector_feasibility_review_items`, `gold_connector_build_queue_summary` | Allow connector artifact generation only through explicit review and evidence paths. |
| Search Intelligence Learning | `company_vocabulary_observations`, `vocabulary_signal_scores`, `search_term_*`, `search_strategy_*`, `capability_gap_scores`, `false_negative_risk_snapshots` | Learn better terms, source gaps, false-negative pressure and candidate signals. |
| Aggregator & Market Sensors | `aggregator_discovery_suppression_*`, `aggregator_novelty_*`, `stepstone_company_discovery_cycle_*`, `company_discovery_cooldowns` | Use aggregators defensively as market sensors and discovery inputs. |
| Origin Observation Learning | `origin_job_observation_runs`, `origin_job_page_observations`, `origin_observed_pattern_candidates`, `origin_pattern_promotion_*`, `origin_observation_seed_pool_snapshots`, `employer_origin_learned_relevance_signals` | Learn reusable origin-page patterns without turning exports or manual lists into pipeline inputs. |
| Orchestration & Actions | `search_intelligence_orchestrator_runs`, `search_intelligence_orchestrator_steps`, `search_intelligence_action_runs` | Record agent/orchestrator steps, dry-run/apply actions and operational attention. |
| Cleanup & Compliance | `employer_origin_candidate_cleanup_audit`, `employer_origin_reprocess_benchmarks` | Audit candidate reset/removal/reprocess operations and benchmark repair loops. |
| Gold / Control Center Views | `gold_*` views, `dashboard_*` views | Provide read models for the Control Center and operator-facing summaries. |

## Constraint families

The schema uses constraints as product safety boundaries, not only as database
technicalities.

| Constraint family | Examples | Why it matters |
|---|---|---|
| Primary keys | Most operational tables use surrogate `id` keys. | Stable internal references and append-only auditability. |
| Foreign keys | `raw_jobs` → `ingestion_runs` / `search_profiles`; gate events → gate reviews; detail evidence → candidates/reviews where applicable. | Prevents orphaned pipeline evidence and broken lifecycle chains. |
| Unique constraints | Search profile names, profile-term combinations, source-local job identity, gate review uniqueness by candidate/gate. | Prevents duplicate ingestion/gate state from corrupting decisions. |
| Check constraints | Gate status, gate decision, stop reason, event type, action/run type vocabularies. | Keeps agent/gate vocabulary explicit and reviewable. |
| Indexes | Source/time indexes, candidate/status indexes, failed-run diagnostics indexes. | Keeps review and dashboard queries practical as the schema grows. |
| Views | `source_heartbeat`, `dashboard_*`, `gold_*`. | Separates operator/read-model shape from raw transactional/audit tables. |

## High-value current tables and views

The following objects are especially important for understanding the current
Search Intelligence system:

| Object | Type | Why a reviewer should care |
|---|---|---|
| `raw_jobs` | Table | Bronze source-preserving truth for fetched jobs. |
| `job_observations` | Table | Repeated sightings without pretending every sighting is a new job. |
| `silver_jobs` | Table | Canonical normalized job layer. |
| `employer_origin_source_candidates` | Table | Candidate companies/origin sources before connector activation. |
| `employer_origin_candidate_gate_reviews` | Table | Gate decisions and stop/review outcomes. |
| `employer_origin_candidate_gate_events` | Table | Audit trail for gate lifecycle changes. |
| `employer_origin_source_discovery_reviews` | Table | Evidence-backed origin/source URL discovery reviews. |
| `employer_origin_url_repair_reviews` | Table | Safe repair path for broken or weak origin URLs. |
| `candidate_origin_url_persistence_reviews` | Table | Review surface before persisting origin URL changes. |
| `employer_origin_job_detail_evidence` | Table | Concrete sample/detail evidence for candidate validation. |
| `connector_feasibility_reviews` | Table | Feasibility evidence before connector-build recommendation. |
| `employer_origin_connector_build_requests` | Table | Approval-gated connector build workflow. |
| `search_intelligence_orchestrator_runs` | Table | Runtime/orchestrator audit root. |
| `search_intelligence_orchestrator_steps` | Table | Step-level orchestrator traceability. |
| `search_intelligence_action_runs` | Table | Dry-run/apply/action run audit surface. |
| `stepstone_company_discovery_cycle_reviews` | Table | Defensive StepStone company-discovery cycle state. |
| `stepstone_company_discovery_cycle_items` | Table | Per-company/term discovery-cycle observations. |
| `origin_job_page_observations` | Table | Origin-page observation results used for pattern learning. |
| `origin_observed_pattern_candidates` | Table | Learned pattern candidates before promotion. |
| `origin_pattern_promotion_runs` | Table | Controlled pattern-promotion runs. |
| `source_heartbeat` | View | Latest source health/readiness signal. |
| `gold_source_health_summary` | View | Source-health read model for Control Center. |
| `gold_connector_build_queue_summary` | View | Connector-build queue read model. |
| `candidate_market_evidence_summary` | View | Candidate evidence summary/read model. |

## What this overview is not

This is not a full generated catalog of every column.

The next maturity step is a schema-inspection report that can be regenerated from
PostgreSQL and checked against this documentation. That should be a generated
report under `exports/` or a runtime command, while this document remains the
human-maintained architecture/reference map.
