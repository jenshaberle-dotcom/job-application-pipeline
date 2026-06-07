# Database Schema Relationships

Status: current schema relationship map
Scope: DOC-001H table/view network overview

## Purpose

This document shows the main database networks behind the Search Intelligence
pipeline. It is deliberately split into smaller Mermaid diagrams so GitHub can
render and reviewers can reason about one domain at a time.

## Ingestion, Bronze and Silver

```mermaid
erDiagram
    search_profiles ||--o{ search_terms : defines
    search_profiles ||--o{ ingestion_runs : executes
    search_terms ||--o{ ingestion_runs : term_lineage
    ingestion_runs ||--o{ raw_jobs : inserts
    search_profiles ||--o{ raw_jobs : profile_lineage
    raw_jobs ||--o{ job_observations : observed_over_time
    raw_jobs ||--o{ silver_processing_decisions : processed_by
    raw_jobs ||--o| silver_jobs : canonicalized_into
    ingestion_runs ||--o{ source_heartbeat : summarized_by
```

Boundary: ingestion creates source-preserving Bronze records first. Silver and
Gold/read models must not erase raw source lineage.

## Employer-Origin Candidate and Gate Network

```mermaid
erDiagram
    employer_origin_source_candidates ||--o{ candidate_profiles : describes
    employer_origin_source_candidates ||--o{ candidate_skills : requires
    employer_origin_source_candidates ||--o{ market_evidence : supported_by
    employer_origin_source_candidates ||--o{ employer_origin_candidate_gate_reviews : reviewed_by
    employer_origin_candidate_gate_reviews ||--o{ employer_origin_candidate_gate_events : emits
    employer_origin_source_candidates ||--o{ candidate_reassessment_queue : may_reenter
    employer_origin_source_candidates ||--o{ candidate_market_evidence_summary : summarized_by
```

Boundary: the gate network is the product's “Türsteher”. It must explain both
positive progression and negative stops with comparable rigor.

## Evidence, URL Discovery and Repair

```mermaid
erDiagram
    employer_origin_source_candidates ||--o{ employer_origin_source_discovery_reviews : source_url_discovery
    employer_origin_source_candidates ||--o{ employer_origin_url_repair_reviews : url_repair
    employer_origin_source_candidates ||--o{ candidate_origin_url_persistence_reviews : persistence_review
    employer_origin_source_candidates ||--o{ employer_origin_job_detail_evidence : detail_evidence
    employer_origin_source_candidates ||--o{ connector_feasibility_reviews : feasibility_review
    connector_feasibility_reviews ||--o{ connector_feasibility_review_items : contains
```

Boundary: weak URLs and weak detail evidence should lead to repair/review states,
not silent connector activation.

## Connector Build and Approval Governance

```mermaid
erDiagram
    employer_origin_source_candidates ||--o{ employer_origin_connector_generation_plans : planned_for
    employer_origin_source_candidates ||--o{ employer_origin_connector_build_requests : approval_gated_build
    employer_origin_connector_build_requests ||--o{ gold_connector_build_queue_summary : summarized_by
    connector_feasibility_reviews ||--o{ employer_origin_connector_build_requests : informs
```

Boundary: generated connector artifacts are not the same as registered or active
connectors. Build, validation and final approval remain separate gates.

## Search Intelligence Learning and Market Sensors

```mermaid
erDiagram
    company_vocabulary_observations ||--o{ vocabulary_signal_scores : scored_as
    search_term_validation_runs ||--o{ search_term_confidence_snapshots : measures
    search_strategy_recommendations ||--o{ search_strategy_trial_terms : proposes
    search_strategy_trial_terms ||--o{ search_strategy_trial_outcomes : evaluated_by
    aggregator_novelty_snapshots ||--o{ aggregator_novelty_items : contains
    stepstone_company_discovery_cycle_reviews ||--o{ stepstone_company_discovery_cycle_items : contains
    stepstone_company_discovery_cycle_reviews ||--o{ company_discovery_cooldowns : controls
```

Boundary: aggregators are market sensors and discovery inputs. They must not turn
into uncontrolled scraping or hidden source-of-truth shortcuts.

## Origin Observation and Pattern Learning

```mermaid
erDiagram
    origin_job_observation_runs ||--o{ origin_job_page_observations : observes
    origin_job_page_observations ||--o{ origin_observed_pattern_candidates : suggests
    origin_pattern_promotion_runs ||--o{ origin_pattern_promotion_decisions : decides
    origin_observation_seed_pool_snapshots ||--o{ origin_job_observation_runs : seeds
    employer_origin_learned_relevance_signals ||--o{ origin_observed_pattern_candidates : informs
```

Boundary: origin observation is a learning system. It should deduplicate known
seeds, detect saturation and use bounded revalidation rather than repeated blind
observation.

## Orchestrator, Actions and Audit

```mermaid
erDiagram
    search_intelligence_orchestrator_runs ||--o{ search_intelligence_orchestrator_steps : contains
    search_intelligence_action_runs ||--o{ search_intelligence_orchestrator_steps : may_trigger
    employer_origin_candidate_cleanup_audit ||--o{ employer_origin_source_candidates : audits_candidate_action
    employer_origin_reprocess_benchmarks ||--o{ employer_origin_source_candidates : benchmarks_reprocess
```

Boundary: dry-run/apply decisions and operator-facing actions need auditability.
This is the foundation for future safe UI actions.

## Current gap

The project has a useful schema map now, but not yet a generated full constraint
catalog.

A later block should add a read-only schema-inspection script that writes an
`exports/` report with:

- tables and views,
- columns and nullability,
- primary keys,
- foreign keys,
- unique constraints,
- check constraints,
- indexes,
- row counts where operationally useful.
