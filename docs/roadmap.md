# Project Roadmap

## Phase 1 — Foundation & Environment

Completed:
- Local WSL2 development environment
- Dockerized PostgreSQL database
- Python virtual environment
- Git + GitHub integration
- SSH authentication
- Secret separation using `.env`
- Dependency management
- Initial project documentation

---

## Phase 2 — Bronze Layer Ingestion

Completed:
- Real-world data source integration
- Bundesagentur für Arbeit ingestion
- Configurable search profiles
- Multi-term search strategy
- Ingestion run tracking
- Raw JSON storage
- Database-level duplicate protection
- Idempotent ingestion behavior

In Progress:
- Multi-source ingestion architecture
- Connector modularization

---

## Phase 3 — Source Evaluation

Planned:
- StepStone integration
- LinkedIn Jobs evaluation
- Greenhouse integration
- Workday integration
- Source capability comparison
- Data structure comparison
- Detail page ingestion

Goals:
- Identify universal job fields
- Identify source-specific fields
- Evaluate ingestion complexity
- Evaluate data quality
- Evaluate anti-bot challenges

---

## Phase 4 — Silver Layer

Planned:
- Job normalization
- Unified job model
- Skill extraction
- Location normalization
- Duplicate consolidation
- Structured metadata extraction

---

## Phase 5 — Semantic Matching

Planned:
- Embedding-based similarity
- CV-to-job matching
- Relevance scoring
- Recommendation engine
- LLM-assisted classification

---

## Phase 6 — Gold Layer & Analytics

Planned:
- Dashboards
- KPIs
- Trend analysis
- Source effectiveness metrics
- Search profile analytics

---

## Phase 7 — Cloud & Productionization

Planned:
- Azure deployment
- Managed secrets
- Scheduling/orchestration
- Monitoring
- CI/CD
- Infrastructure as Code
