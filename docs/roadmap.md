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
- Connector-based ingestion architecture
- Source-specific connector isolation
- Repository-based Bronze-layer persistence
- Ingestion runner orchestration

In Progress:
- Additional connector candidates
- Multi-source architecture validation

---

## Phase 3 — Source Evaluation

Completed:
- Initial source evaluation strategy
- Greenhouse selected as next connector candidate
- Greenhouse source analysis

Planned:
- StepStone integration evaluation
- LinkedIn Jobs evaluation
- Workday integration evaluation
- Company career page evaluation

Goals:
- Identify universal job fields
- Identify source-specific fields
- Evaluate ingestion complexity
- Evaluate data quality
- Evaluate anti-bot challenges
- Compare easy API-based sources with harder real-world sources
- Include sources with different access patterns such as public APIs, HTML pages, ATS platforms, and company career pages
- Avoid overfitting the architecture to the Bundesagentur für Arbeit API
- Decide which source should become the next production-style connector

---

## Phase 4 — Silver Layer

Completed:
- Initial canonical `silver_jobs` table
- Initial Bronze-to-Silver transformation
- Traceability from Silver records back to raw Bronze records

Planned:
- Expanded job normalization
- Unified job representation
- Skill extraction
- Location normalization
- Company normalization
- Duplicate consolidation across sources
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
- Search term effectiveness analytics

---

## Phase 7 — Cloud & Productionization

Planned:
- Azure deployment
- Managed secrets
- Scheduling/orchestration
- Monitoring
- CI/CD
- Infrastructure as Code
