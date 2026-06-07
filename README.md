# Job Application Pipeline

## Vision

This project aims to build an automated multi-source job market intelligence and application workflow platform.

The goal is to collect job postings from realistic sources, store them in a structured data platform, track their lifecycle over time, normalize relevant jobs and prepare them for matching, analytics and future visualization.

The project is designed as both:

- [x] a personal learning journey towards Data Engineering
- [x] a production-oriented showcase project
- [x] a realistic portfolio project based on heterogeneous real-world sources
- [ ] a future API-first dashboard and application workflow system

The focus is intentionally placed on:

- realistic data sources
- maintainable architecture
- reproducible environments
- pragmatic security concepts
- explainable engineering decisions
- source-aware ingestion behavior
- lifecycle-aware job observations
- future dashboard and workflow readiness


---

## Platform Identity

The project uses a defined visual and communication style named **Deep Ocean Intelligence**.

The style is intended to make project diagrams, dashboard mockups, presentation assets and future frontend work feel like one coherent data platform product.

Core principles:

- calm technical competence
- source value over raw volume
- defensive and transparent source acquisition
- clear distinction between implemented features, active work and future vision
- consistent visual treatment of Sources, Bronze, Silver, Gold and API/UI layers
- dashboard language in English, reflective project narrative in German where useful

Visual and documentation rules are tracked in:

- [`docs/design/README.md`](docs/design/README.md)
- [`docs/design/visual_identity.md`](docs/design/visual_identity.md)
- [`docs/adr/031_define_platform_visual_identity.md`](docs/adr/031_define_platform_visual_identity.md)

---

## Architecture

<!-- DOC-001-DOC-002-OPERATING-BASELINE:START -->
## Current Operating Baseline

The project now treats governance and current-state documentation as part of the product surface.

Current repo-level operating documents:

- [`docs/governance/governance_foundation.md`](docs/governance/governance_foundation.md) — DOC-001 lightweight governance gate.
- [`docs/governance/documentation_drift_baseline.md`](docs/governance/documentation_drift_baseline.md) — DOC-002 documentation drift baseline.
- [`docs/architecture/search_intelligence_current_state.md`](docs/architecture/search_intelligence_current_state.md) — current Search Intelligence operating snapshot.
- [`docs/planning/eo002b_candidate_reprocessing_url_finder_validation.md`](docs/planning/eo002b_candidate_reprocessing_url_finder_validation.md) — next validation campaign.

The immediate sequence is:

```text
DOC-001 Governance Foundation Gate
→ DOC-002 Documentation Drift Baseline
→ EO-002B Candidate Reprocessing & URL Finder Validation
→ EO-002B Metrics & Decision Report
→ Wave Search Intelligence + Scheduler/Orchestrator validation
→ Large Adrian-quality documentation/design polish
```

Status language must distinguish implemented code from operationally validated behavior. Search Intelligence features that are built but not yet proven in realistic runs must be documented as such.
<!-- DOC-001-DOC-002-OPERATING-BASELINE:END -->

The pipeline follows a layered data architecture inspired by modern data platforms and Microsoft Fabric concepts.

Architecture flow:

- Source Connectors
- Bronze Layer
- Relevance / Processing Decisions
- Silver Layer
- Gold / Analytical Views
- Future API
- Future Frontend

### Bronze Layer

Raw ingestion and observation layer.

Stores:

- original API responses
- raw job postings as JSON
- unmodified source data
- ingestion metadata
- ingestion history
- source-local job observations over time

Current Bronze-related tables:

- `search_profiles`
- `search_terms`
- `ingestion_runs`
- `raw_jobs`
- `job_observations`

### Silver Layer

Initial normalization, relevance and canonicalization layer.

Currently contains:

- canonical `silver_jobs` table
- source-aware transformation from Bronze records
- traceability back to `raw_jobs`
- relevance filtering
- processing decisions for included and skipped jobs

Current Silver-related tables:

- `silver_jobs`
- `silver_processing_decisions`

Will later contain:

- cleaned job titles
- normalized locations
- normalized companies
- role-family classification
- extracted skills
- semantic duplicate candidates
- structured metadata

### Gold Layer

Planned analytics and serving layer.

Will contain:

- dashboard-oriented views
- lifecycle analytics
- source health views
- role and skill aggregations
- matching scores
- recommendation logic
- reporting datasets
- API-oriented analytical datasets

### Future API and Frontend

Planned application layer.

Target architecture:

- FastAPI backend
- React frontend
- local Docker-based development
- optional later cloud deployment

Planned capabilities:

- source health dashboard
- top daily job recommendations
- application workflow tracking
- interactive application status updates
- historical job market visualizations
- source and role-family distributions
- skill and requirement heatmaps

---

## Current Tech Stack

### Infrastructure

- [x] Windows 11
- [x] WSL2
- [x] Ubuntu 24.04
- [x] Docker Desktop

### Backend / Data

- [x] PostgreSQL 17
- [x] Python 3.12
- [x] psycopg
- [x] requests
- [x] python-dotenv

### Version Control

- [x] Git
- [x] GitHub
- [x] Pull-request based development workflow

### Security / Credential Management

- [x] `.env` based local configuration
- [x] `.gitignore` based secret exclusion
- [x] Bitwarden
- [x] Ente Auth
- [x] SSH authentication

### Future Application Stack

- [ ] FastAPI
- [ ] React
- [ ] API schemas
- [ ] frontend components
- [ ] local API/frontend Docker setup
- [ ] optional cloud deployment

---

## Current Status

### Implemented

- [x] Local Linux development environment using WSL2
- [x] Dockerized PostgreSQL database
- [x] Python virtual environment
- [x] PostgreSQL connection from Python
- [x] GitHub repository integration
- [x] SSH based GitHub authentication
- [x] Environment based configuration using `.env`
- [x] Initial Bronze Layer implementation
- [x] Real-world job ingestion pipeline
- [x] Raw job ingestion from the German Federal Employment Agency job search
- [x] Greenhouse ATS ingestion
- [x] Limited StepStone result-card ingestion
- [x] Personio XML ingestion
- [x] Database-level duplicate protection
- [x] Idempotent ingestion behavior using PostgreSQL constraints
- [x] Search profile driven ingestion
- [x] Multi-term search strategy
- [x] Search-term lineage on ingestion runs
- [x] Ingestion run tracking
- [x] Connector-based ingestion architecture
- [x] Source-specific connector isolation
- [x] Explicit source capability modeling
- [x] Canonical search intent architecture
- [x] Source target acquisition model
- [x] Local post-fetch filtering for non-search-capable sources
- [x] Repository-based Bronze-layer persistence
- [x] Ingestion runner orchestration
- [x] Job observation tracking
- [x] Run-level job observation semantics
- [x] Initial Silver-layer table
- [x] Initial Bronze-to-Silver transformation
- [x] Greenhouse Silver transformation
- [x] Personio Silver transformation
- [x] StepStone Silver transformation
- [x] First Canonicalization Layer for Silver jobs
- [x] Canonical key candidate generation
- [x] Relevance filtering for Silver candidates
- [x] Token-aware relevance matching
- [x] Silver processing decision tracking
- [x] Silver source value exploration script
- [x] Ingestion failure diagnostics
- [x] Minimal ingestion logging baseline
- [x] Source family, source target and source type decision
- [x] Separation of technical duplicate protection and semantic deduplication
- [x] Detailed PostgreSQL schema documentation
- [x] Constraint and index documentation
- [x] Bronze/Silver ERD documentation
- [x] Connector capability comparison documentation
- [x] Source evaluation documentation
- [x] Greenhouse source analysis
- [x] StepStone source analysis
- [x] Personio source analysis
- [x] Search result connector contract documentation
- [x] Relevance strategy documentation
- [x] API-first dashboard architecture planning
- [x] Visualization vision documentation
- [x] Architecture documentation
- [x] Mermaid-based architecture diagrams
- [x] Architecture Decision Records
- [x] Employer-origin connector generation planning foundation

### In Progress

- [~] Documentation consistency review
- [~] Source target lineage design
- [~] Observation granularity refinement
- [~] Gold-layer preparation
- [~] Source value and search quality evaluation

### Planned

- [ ] Explicit source-target lineage in ingestion runs
- [ ] Controlled Greenhouse source-target expansion
- [ ] Additional ATS and company-board source evaluation
- [~] Controlled Personio Batch 1 source-value validation
- [ ] Softgarden evaluation
- [ ] SmartRecruiters evaluation
- [ ] Workday and SAP SuccessFactors exploration
- [ ] Expanded Silver layer normalization
- [ ] Role-family classification
- [ ] Skill extraction
- [ ] Matching engine
- [ ] Dashboard-oriented Gold views
- [ ] FastAPI backend
- [ ] React frontend
- [ ] Source health monitoring
- [ ] Application workflow tracking
- [ ] Cloud deployment
- [ ] Cross-source semantic deduplication
- [ ] Canonical job identity modeling

### Current Direction

The project is evolving from a job ingestion pipeline into a personal job market intelligence platform focused on:

- multi-source ingestion
- canonical modeling
- lifecycle tracking
- historical analytics
- semantic matching
- market intelligence
- dashboard-oriented Gold datasets
- better Ground Truth expansion through bounded employer-origin connector generation
- personal application workflow support

The architecture is increasingly optimized for heterogeneous real-world source behavior where:

- some sources support strong server-side filtering
- some sources only support full-board fetches
- some sources require local filtering after ingestion
- some sources provide richer publication metadata than others
- some sources require source-specific normalization

The project intentionally models these differences explicitly instead of hiding them behind artificial abstractions.

---

## Bronze Layer Data Model

### search_profiles

Defines configurable ingestion search profiles.

Contains:

- search strategy metadata
- locations
- search radius
- source information
- activation state

### search_terms

Contains multiple search terms per search profile.

Allows:

- broader market coverage
- configurable search strategies
- ingestion experimentation
- future analytics on search effectiveness

### ingestion_runs

Tracks every ingestion execution.

Contains:

- runtime metadata
- execution timestamps
- ingestion statistics
- status information
- requested URLs

### raw_jobs

Stores raw job postings and ingestion references.

Contains:

- raw API payloads
- source metadata
- external identifiers
- ingestion references
- search profile references

### job_observations

Tracks repeated sightings of source-local jobs during ingestion runs.

Supports future analysis of:

- first seen date
- last seen date
- number of runs seen
- observed job availability
- source activity over time
- approximate lifecycle analysis

Important distinction:

`first_seen_at` means first observed by this pipeline.

It does not necessarily mean the original publication date.

### Database Documentation

Detailed database documentation is available in:

- `docs/diagrams/bronze_data_model.md`
- `docs/database/tables.md`

The documentation includes:

- ERD relationships
- primary keys
- foreign keys
- indexes
- unique constraints
- lineage rationale
- duplicate handling rationale
- observation semantics
- current design limitations
- future extension considerations

---

## Data Source Strategy

The project intentionally uses realistic job market data sources instead of tutorial/demo APIs.

Current implemented sources:

- [x] Bundesagentur für Arbeit
- [x] Greenhouse ATS
- [x] Limited StepStone result-card ingestion
- [x] Personio XML ingestion

Current source-value validation focus:

- [~] Controlled Personio Batch 1 evaluation
- [~] Source overlap and company coverage comparison

Prepared or planned sources:

- [ ] Controlled Greenhouse source-target expansion
- [ ] Softgarden evaluation
- [ ] SmartRecruiters evaluation
- [ ] Workday and SAP SuccessFactors exploration
- [ ] direct company career pages

Reasons for this decision:

- realistic German labor market data
- relevant regional search capability
- real-world API structures
- realistic ingestion challenges
- duplicate handling requirements
- lifecycle tracking requirements
- production-oriented data quality problems

The project prioritizes:

- realistic engineering problems
- explainable architectural decisions
- scalable data ingestion patterns
- source-specific capability modeling
- lifecycle-aware analytics

over artificially simplified tutorial scenarios.

### Source Capability Modeling

The project explicitly models differences between source capabilities.

Examples:

- some APIs support keyword search
- some APIs support location and radius filtering
- some ATS systems only support full-board fetches
- some platforms require local filtering after ingestion

The ingestion layer therefore separates:

- canonical search intent
- source-specific connector behavior
- local post-fetch filtering
- source capability metadata

Current implemented examples:

| Source family | Keyword | Location | Radius | Pagination | Full Fetch | Local Filter |
|---|---:|---:|---:|---:|---:|---:|
| Bundesagentur für Arbeit | yes | yes | yes | yes | no | no |
| Greenhouse | no | no | no | no | yes | yes |
| StepStone | yes | yes | no | limited | no | yes |
| Personio | no | no | no | no | yes | yes |

## Repository Structure

Migration prefixes have been normalized. See ADR-018.

```text
job-application-pipeline/
├── db/
│   ├── migrations/
│   │   ├── 001_bronze_ingestion_model.sql
│   │   ├── 002_search_terms_model.sql
│   │   ├── 003_silver_jobs_model.sql
│   │   ├── 004_make_search_profiles_source_agnostic.sql
│   │   ├── 005_silver_processing_decisions.sql
│   │   ├── 006_job_observations.sql
│   │   ├── 007_job_observations_run_level_unique.sql
│   │   ├── 008_job_lifecycle_view.sql
│   │   ├── 009_source_heartbeat_view.sql
│   │   ├── 010_dashboard_new_relevant_jobs_view.sql
│   │   ├── 011_dashboard_source_processing_summary_view.sql
│   │   ├── 012_add_stepstone_search_profile.sql
│   │   ├── 013_add_search_term_lineage_to_ingestion_runs.sql
│   │   ├── 014_extend_silver_jobs_for_canonicalization.sql
│   │   ├── 015_add_personio_schluetersche_search_profile.sql
│   │   ├── 016_add_personio_batch_1_search_profiles.sql
│   │   └── 017_add_ingestion_run_diagnostics.sql
│   │
│   └── queries/
│
├── docs/
│   ├── adr/
│   │   ├── README.md
│   │   ├── 001_use_real_job_market_sources.md
│   │   ├── 002_use_bronze_first_architecture.md
│   │   ├── 003_use_database_level_duplicate_protection.md
│   │   ├── 004_use_search_profile_based_ingestion.md
│   │   ├── 005_use_postgresql_as_primary_database.md
│   │   ├── 006_use_dockerized_local_development.md
│   │   ├── 007_use_ssh_for_github_authentication.md
│   │   ├── 008_use_environment_based_configuration.md
│   │   ├── 009_use_connector_based_ingestion.md
│   │   ├── 010_define_canonical_job_model_for_silver_layer.md
│   │   ├── 011_separate_technical_duplicates_from_cross_source_deduplication.md
│   │   ├── 012_prepare_bronze_layer_for_historical_job_observations.md
│   │   ├── 013_evolve_toward_a_personal_job_market_intelligence_platform.md
│   │   ├── 014_document_database_schema_and_constraints.md
│   │   ├── 015_use_canonical_search_intent_and_source_capabilities.md
│   │   ├── 016_define_ingestion_scope_and_relevance_boundaries.md
│   │   ├── 017_prepare_api_first_dashboard_architecture.md
│   │   ├── 018_preserve_existing_migration_ordering.md
│   │   ├── 019_separate_source_heartbeat_from_ingestion_runs.md
│   │   ├── 020_introduce_role_family_classification.md
│   │   ├── 021_expand_source_capability_model_before_complex_sources.md
│   │   ├── 022_define_shared_source_and_layer_terminology.md
│   │   ├── 023_define_search_result_connector_contract.md
│   │   ├── 024_define_search_quality_and_relevance_evaluation_boundary.md
│   │   ├── 025_preserve_search_term_lineage_for_quality_evaluation.md
│   │   ├── 026_define_source_acquisition_scope_and_canonical_source_strategy.md
│   │   ├── 027_define_source_target_acquisition_model.md
│   │   └── 028_separate_source_family_target_and_type.md
│   │
│   ├── classification/
│   │   └── role_family_classification.md
│   │
│   ├── data_sources/
│   │   ├── search_result_connector_contract.md
│   │   └── source_capabilities.md
│   │
│   ├── database/
│   │   └── tables.md
│   │
│   ├── development/
│   │   ├── documentation_consistency_review.md
│   │   └── testing.md
│   │
│   ├── diagrams/
│   │   ├── architecture.md
│   │   └── bronze_data_model.md
│   │
│   ├── observability/
│   │   └── source_health_and_heartbeat.md
│   │
│   ├── planning/
│   │   └── relevance_and_search_quality.md
│   │
│   ├── relevance/
│   │   └── relevance_strategy.md
│   │
│   ├── source_analysis/
│   │   ├── greenhouse.md
│   │   ├── greenhouse_api_examples.md
│   │   ├── personio.md
│   │   └── stepstone.md
│   │
│   ├── visualization/
│   │   └── dashboard_vision.md
│   │
│   ├── glossary.md
│   ├── roadmap.md
│   └── source_evaluation.md
│
├── scripts/
│   ├── __init__.py
│   ├── analyze_greenhouse_bronze.py
│   ├── analyze_stepstone_result_boundaries.py
│   ├── analyze_stepstone_source.py
│   ├── analyze_stepstone_structured_cards.py
│   ├── backfill_silver_canonicalization_fields.py
│   ├── explore_silver_source_value.py
│   ├── inspect_personio_pipeline_state.py
│   ├── preview_personio_xml_targets.py
│   ├── preview_stepstone_result_card_records.py
│   └── show_ingestion_run_summary.py
│
├── src/
│   ├── connectors/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── bundesagentur.py
│   │   ├── capabilities.py
│   │   ├── greenhouse.py
│   │   ├── personio.py
│   │   ├── stepstone.py
│   │   └── stepstone_result_cards.py
│   │
│   ├── ingestion/
│   │   ├── __init__.py
│   │   ├── diagnostics.py
│   │   ├── post_fetch_filter.py
│   │   ├── repository.py
│   │   └── runner.py
│   │
│   ├── silver/
│   │   ├── __init__.py
│   │   ├── relevance.py
│   │   ├── repository.py
│   │   └── transformer.py
│   │
│   ├── config.py
│   ├── ingest_jobs.py
│   ├── main.py
│   └── run_silver_jobs.py
│
├── .env.example
├── .gitignore
├── tests/
│   ├── fixtures/
│   ├── test_ingest_jobs_cli.py
│   ├── test_ingestion_diagnostics.py
│   ├── test_ingestion_runner_display.py
│   ├── test_personio_connector.py
│   ├── test_silver_transformer_canonicalization.py
│   ├── test_stepstone_connector.py
│   └── test_stepstone_result_cards.py
│
├── docker-compose.yml
├── pytest.ini
├── README.md
├── requirements-dev.txt
└── requirements.txt
```

---

## Documentation

Detailed project documentation is available in:

| Area | Location |
|---|---|
| Architecture Decision Records | `docs/adr/` |
| Database schema documentation | `docs/database/` |
| Architecture diagrams | `docs/diagrams/` |
| Source capability analysis | `docs/data_sources/` |
| Source evaluations | `docs/source_analysis/` |
| Relevance strategy | `docs/relevance/` |
| Project roadmap | `docs/roadmap.md` |
| Dashboard vision | `docs/visualization/` |
| Glossary | `docs/glossary.md` |

---

## Development Approach

The project intentionally prioritizes:

- realistic engineering challenges
- explainable architecture decisions
- production-oriented data modeling
- source-aware ingestion behavior
- maintainable incremental evolution

The architecture explicitly models differences between heterogeneous real-world job sources instead of hiding them behind artificial abstractions.

---

## Current Focus

Current engineering focus areas include:

- validating source value with controlled Personio Batch 1 data
- expanding source coverage defensively and with explicit source-target boundaries
- improving Silver-layer normalization and source overlap analysis
- preparing lifecycle-aware analytics and Gold datasets
- enabling future dashboard and API layers
- preparing semantic matching and deduplication

---

## Quickstart

### Requirements

- Windows 11 with WSL2
- Ubuntu 24.04
- Docker Desktop
- Python 3.12
- Git

### Local Environment Setup

Clone the repository:

    git clone git@github.com:jenshaberle-dotcom/job-application-pipeline.git
    cd job-application-pipeline

Create and activate a virtual environment:

    python3 -m venv .venv
    source .venv/bin/activate

Install dependencies:

    pip install -r requirements.txt

Create a local `.env` file:

    POSTGRES_DB=job_pipeline
    POSTGRES_USER=job_user
    POSTGRES_PASSWORD=job_password
    POSTGRES_HOST=localhost
    POSTGRES_PORT=5432

Start PostgreSQL using Docker:

    docker compose up -d

### Example Commands

Run all active ingestion profiles:

    python -m src.ingest_jobs

Run all active profiles for one source family:

    python -m src.ingest_jobs --source bundesagentur_fuer_arbeit
    python -m src.ingest_jobs --source greenhouse
    python -m src.ingest_jobs --source personio

Run one specific search profile:

    python -m src.ingest_jobs --profile ba_data_engineer_30629_50km
    python -m src.ingest_jobs --profile greenhouse_stripe
    python -m src.ingest_jobs --profile greenhouse_contentful

List active search profiles:

    python -m src.ingest_jobs --list-profiles

Run Silver normalization:

    python -m src.run_silver_jobs

Install development and test dependencies:

    python -m pip install -r requirements-dev.txt

Testing details:

    docs/development/testing.md

Run tests:

    python -m pytest -q


### Search Intelligence Review Commands

Preview bounded StepStone / aggregator novelty from existing market evidence:

    python -m scripts.run_aggregator_novelty_loop_agent --source-name stepstone --days 14 --limit 500

Persist a reviewed aggregator novelty snapshot:

    python -m scripts.run_aggregator_novelty_loop_agent --source-name stepstone --days 14 --limit 500 --reviewed-by jens --write


Start the Search Intelligence Control Center UI for active connectors, candidates, build approvals and the full discovery-to-approval chain:

    python -m scripts.run_search_intelligence_control_center

Enable local token-gated approval actions:

    python -m scripts.run_search_intelligence_control_center --allow-write-actions --reviewed-by jens


---

## Disclaimer

This project is a personal educational and portfolio project.

It is intentionally designed around realistic engineering challenges and publicly accessible job market sources.

Future source integrations are evaluated individually based on:

- technical feasibility
- maintainability
- architectural value
- operational complexity
- legal and ethical considerations

### S6C Approval-Gated Connector Build

S6C connects unresolved high-pressure employer-origin candidates to a controlled connector-artifact build path. It can write DB-backed build requests and, after explicit build approval, generate bounded connector candidate artifacts. It still does not register connectors, activate sources, write Bronze rows or change schedules.

<!-- ARCH-001-SAFETY-SECURITY-STATE:START -->
## Architecture Freeze and Safety/Security Baseline

The project is now in architecture-freeze / maturity mode.

Active work should close architecture contracts, fix measured pipeline gaps or improve measurability. New ideas are parked unless they are expected to improve a clearly named maturity area by roughly 15 to 20 points.

ARCH-001 defines the current safety, security and pipeline-state baseline:

- safety zones from read-only analysis to destructive/compliance operations
- agent permission matrix
- candidate lifecycle state machine
- gate contract baseline
- security baseline for external requests, secrets and reports
- 90+ maturity campaign path

Primary documents:

- docs/architecture/safety_security_state_architecture.md
- docs/architecture/agent_permission_matrix.md
- docs/architecture/pipeline_state_machine.md
- docs/architecture/gate_contract_baseline.md
- docs/security/search_intelligence_security_baseline.md
- docs/planning/architecture_freeze_maturity_campaign.md
- docs/adr/033_define_search_intelligence_safety_security_boundaries.md
<!-- ARCH-001-SAFETY-SECURITY-STATE:END -->

<!-- EO-002E-GATE-STOP-NEXT-SAFE:START -->
## EO-002E Gate Stop / Next-Safe-Action Evidence Analysis

EO-002E adds a read-only report for the step after URL Finder validation. It compares selected URLs from EO-002B/EO-002D reports with persisted candidate URLs and gate state, then recommends the next safe action without writing to the database.

Use it to decide whether the next maturity work should persist a selected URL under SZ1 review, run bounded gate/evidence analysis under SZ2, or stop for manual review.
<!-- EO-002E-GATE-STOP-NEXT-SAFE:END -->

<!-- BEGIN CAND-001-VALIDATED-ORIGIN-URL-PERSISTENCE -->
### CAND-001 Validated Origin URL Persistence Gate

CAND-001 provides the reviewed SZ1 transition from live URL-Finder validation to persisted `candidate_url`. It keeps URL-Finder exports as review context only and avoids using local report files as hidden pipeline inputs.
<!-- END CAND-001-VALIDATED-ORIGIN-URL-PERSISTENCE -->

<!-- BEGIN GATE-001-README -->
### GATE-001 Initial Gate Review Foundation

The project now includes a dry-run-first initial gate review layer for persisted employer-origin candidate URLs. It evaluates source discovery, technical reachability and risk gates before downstream detail evidence discovery.
<!-- END GATE-001-README -->
