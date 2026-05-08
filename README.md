# Job Application Pipeline

## Vision

This project aims to build an automated end-to-end job ingestion and analysis pipeline.

The goal is to collect job postings from multiple sources, store them in a structured data platform, remove duplicates, normalize content and evaluate job postings based on custom matching criteria.

The project is designed as both:
- a personal learning journey towards Data Engineering
- and a production-oriented showcase project

The focus is intentionally placed on:
- realistic data sources
- maintainable architecture
- reproducible environments
- pragmatic security concepts
- explainable engineering decisions

---

## Architecture

The pipeline follows a layered data architecture inspired by modern data platforms and Microsoft Fabric concepts.

### Bronze Layer

Raw ingestion layer.

Stores:
- original API responses
- raw job postings as JSON
- unmodified source data
- ingestion metadata
- ingestion history

Current Bronze Layer tables:
- `search_profiles`
- `search_terms`
- `ingestion_runs`
- `raw_jobs`

### Silver Layer

Initial normalization and transformation layer.

Currently contains:
- first canonical `silver_jobs` table
- source-aware transformation from Bronze records
- traceability back to `raw_jobs`

Will later contain:
- cleaned job titles
- normalized locations
- extracted skills
- duplicate detection
- standardized company data

### Gold Layer

Planned analytics and matching layer.

Will contain:
- matching scores
- skill heatmaps
- recommendation logic
- reporting datasets
- ranking and relevance calculations

---

## Current Tech Stack

### Infrastructure
- Windows 11
- WSL2
- Ubuntu 24.04
- Docker Desktop

### Backend / Data
- PostgreSQL 17
- Python 3.12
- psycopg
- requests
- python-dotenv

### Version Control
- Git
- GitHub

### Security / Credential Management
- Bitwarden
- Ente Auth
- SSH Authentication

---

## Current Status

Implemented:
- Local Linux development environment using WSL2
- Dockerized PostgreSQL database
- Python virtual environment
- PostgreSQL connection from Python
- GitHub repository integration
- SSH based GitHub authentication
- Environment based configuration using `.env`
- Initial Bronze Layer implementation
- Real-world job ingestion pipeline
- Raw job ingestion from the German Federal Employment Agency job search
- Database-level duplicate protection
- Idempotent ingestion behavior using PostgreSQL constraints
- Search profile driven ingestion
- Multi-term search strategy
- Ingestion run tracking
- Connector-based ingestion architecture
- Source-specific connector isolation
- Repository-based Bronze-layer persistence
- Ingestion runner orchestration
- Initial Silver-layer table
- Initial Bronze-to-Silver transformation
- Source evaluation documentation
- Greenhouse source analysis
- Architecture documentation
- Mermaid-based architecture diagrams
- Architecture Decision Records (ADRs)

In Progress:
- Greenhouse connector evaluation
- Additional connector candidates
- Multi-source architecture validation

Planned:
- Additional production-style connectors
- Expanded Silver layer normalization
- Matching engine
- Dashboard / visualization
- Cloud deployment

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

---

## Data Source Strategy

The project intentionally uses realistic job market data sources instead of tutorial/demo APIs.

The first ingestion source is the German Federal Employment Agency job search.

Planned additional sources:
- StepStone
- LinkedIn Jobs
- Greenhouse ATS
- Workday-based career systems

Reasons for this decision:
- realistic German labor market data
- relevant regional search capability
- real-world API structures
- realistic ingestion challenges
- duplicate handling requirements
- production-oriented data quality problems

The project prioritizes:
- realistic engineering problems
- explainable architectural decisions
- scalable data ingestion patterns

over artificially simplified tutorial scenarios.

## Repository Structure

```text
job-application-pipeline/
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
│   │   └── 010_define_canonical_job_model_for_silver_layer.md
│   │
│   ├── diagrams/
│   │   ├── architecture.md
│   │   └── bronze_data_model.md
│   │
│   ├── source_analysis/
│   │   ├── greenhouse.md
│   │   └── greenhouse_api_examples.md
│   │
│   ├── glossary.md
│   ├── roadmap.md
│   └── source_evaluation.md
│
├── db/
│   └── migrations/
│       ├── 001_bronze_ingestion_model.sql
│       ├── 002_search_terms_model.sql
│       └── 003_silver_jobs_model.sql
│
├── src/
│   ├── connectors/
│   │   ├── base.py
│   │   └── bundesagentur.py
│   │
│   ├── ingestion/
│   │   ├── repository.py
│   │   └── runner.py
│   │
│   ├── silver/
│   │   ├── repository.py
│   │   └── transformer.py
│   │
│   ├── config.py
│   ├── ingest_jobs.py
│   ├── run_silver_jobs.py
│   └── main.py
```
---

## Setup

### Clone repository

```bash
git clone git@github.com:jenshaberle-dotcom/job-application-pipeline.git
```

### Create Python virtual environment

```bash
python3 -m venv .venv
```

### Activate virtual environment

```bash
source .venv/bin/activate
```

### Install dependencies

```bash
pip install -r requirements.txt
```

### Start PostgreSQL container

```bash
docker compose up -d
```

### Run ingestion pipeline

```bash
python src/ingest_jobs.py
```

---

## Optional Developer Tools

```bash
sudo apt install tree
```

Useful for visualizing local repository structures during development.

---

## Environment Configuration

Create a local `.env` file based on `.env.example`.

Example:

```env
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=job_pipeline
POSTGRES_USER=your_username
POSTGRES_PASSWORD=your_password
```

Secrets are intentionally excluded from version control via `.gitignore`.

Local credentials are managed using:
- `.env` files for runtime configuration
- Bitwarden for credential storage
- separate MFA protection for secure access

The current setup is optimized for local development.

Future cloud deployments may use:
- Azure Application Settings
- centralized secret management
- Azure Key Vault with Managed Identity

---

## Ingestion Strategy

The ingestion pipeline is designed around configurable search profiles.

Instead of relying on a single narrow search term, the pipeline ingests broader datasets and later evaluates relevance using matching and scoring logic.

This allows:
- broader market coverage
- duplicate analysis
- relevance scoring
- profile optimization
- recommendation logic

The current implementation uses:
- profile-based ingestion
- multiple search terms per profile
- ZIP code based regional search
- configurable search radius

Future iterations may include:
- multiple data sources
- scheduling
- incremental updates
- change tracking
- semantic matching

---

## Duplicate Handling Strategy

The project currently uses technical duplicate protection based on:
- `source_name`
- `external_job_id`

Duplicate protection is enforced at the database level using a PostgreSQL unique index.

This ensures:
- idempotent ingestion behavior
- consistent data integrity
- protection against duplicate inserts
- scalable ingestion behavior for future schedulers and parallel processing

The ingestion pipeline currently uses:

```sql
ON CONFLICT DO NOTHING
```

to safely ignore already ingested job postings.

Future iterations may introduce:
- change detection
- version tracking
- historical snapshots
- soft deletion handling
- fuzzy duplicate detection across multiple platforms

---

## Documentation Strategy

The project documents major engineering and architecture decisions using:
- Architecture Decision Records (ADRs)
- Mermaid architecture diagrams
- Roadmaps
- Structured repository documentation

The goal is to preserve:
- architectural reasoning
- design tradeoffs
- implementation decisions
- project evolution over time

---

## Roadmap

- [x] Local development environment
- [x] Dockerized PostgreSQL
- [x] Python database connection
- [x] GitHub integration
- [x] SSH authentication
- [x] Environment based configuration
- [x] Initial real-world job ingestion
- [x] Database-level duplicate protection
- [x] Search profile based ingestion
- [x] Multi-term search strategy
- [x] Ingestion run tracking
- [x] ADR documentation
- [x] Mermaid architecture diagrams
- [x] Connector abstraction layer
- [ ] Multi-source ingestion
- [x] Source capability evaluation
- [x] Initial Silver layer transformation
- [ ] Canonical normalization expansion
- [ ] Cross-source deduplication
- [ ] Skill extraction
- [ ] Matching engine
- [ ] Dashboard / visualization
- [ ] Cloud deployment

---

## Disclaimer

This repository is currently an active learning and engineering project.

Architecture, tooling and implementation details may evolve over time.
