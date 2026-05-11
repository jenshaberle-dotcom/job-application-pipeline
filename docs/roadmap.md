# Project Roadmap

## Phase 1 — Foundation & Environment

- [x] Local WSL2 development environment
- [x] Dockerized PostgreSQL database
- [x] Python virtual environment
- [x] Git + GitHub integration
- [x] SSH authentication
- [x] Secret separation using `.env`
- [x] Dependency management
- [x] Initial project documentation

---

## Phase 2 — Bronze Layer Ingestion

- [x] Bundesagentur für Arbeit connector
- [x] Greenhouse connector
- [x] Connector-based ingestion architecture
- [x] Source capability abstraction
- [x] Configurable search profiles
- [x] Multi-term search strategy
- [x] Repository-based persistence
- [x] Ingestion runner orchestration
- [x] Ingestion run tracking
- [x] Raw JSON Bronze storage
- [x] Database-level duplicate protection
- [x] Idempotent ingestion behavior
- [x] Local keyword post-filtering
- [x] Job observation tracking
- [x] Observation-based lifecycle preparation

- [~] Multi-source architecture validation
- [~] Observation granularity refinement

- [ ] StepStone connector
- [ ] LinkedIn Jobs evaluation
- [ ] Workday connector
- [ ] Company career page ingestion
- [ ] Anti-bot handling strategy
- [ ] Content hash strategy
- [ ] Source change detection

Goals:

- Support heterogeneous real-world job sources
- Avoid source-specific overfitting
- Preserve raw source payloads
- Build stable ingestion lineage
- Support future lifecycle analytics
- Support future semantic deduplication

---

## Phase 3 — Source Evaluation

- [x] Initial source evaluation strategy
- [x] Greenhouse source analysis
- [x] Capability-based source abstraction

- [ ] Evaluate additional ATS providers
- [ ] Compare structured vs. semi-structured sources
- [ ] Evaluate anti-bot complexity
- [ ] Evaluate operational stability per source
- [ ] Evaluate maintenance cost per source

Goals:

- Identify universal job fields
- Identify source-specific metadata
- Compare ingestion complexity
- Compare data quality
- Compare operational complexity

---

## Phase 4 — Silver Layer

- [x] Initial `silver_jobs` table
- [x] Initial Bronze-to-Silver transformation
- [x] Traceability from Silver back to Bronze
- [x] Initial relevance filtering
- [x] Processing decision tracking
- [x] Token-aware relevance matching

- [~] Lifecycle-oriented Silver preparation

- [ ] Expanded normalization
- [ ] Unified cross-source job representation
- [ ] Location normalization
- [ ] Company normalization
- [ ] Role-family classification
- [ ] Skill extraction
- [ ] Semantic duplicate consolidation
- [ ] Structured metadata extraction

Goals:

- Build stable canonical job representations
- Separate ingestion from analytical datasets
- Prepare lifecycle-aware job intelligence
- Prepare future Gold analytics

---

## Phase 5 — Semantic Matching

- [ ] Embedding-based similarity
- [ ] CV-to-job matching
- [ ] Relevance scoring
- [ ] Recommendation engine
- [ ] LLM-assisted classification
- [ ] Semantic duplicate detection
- [ ] Skill similarity analysis

Goals:

- Improve relevance quality
- Support personalized recommendations
- Support semantic analytics
- Support intelligent ranking

---

## Phase 6 — Gold Layer & Analytics

- [ ] Dashboard-oriented Gold views
- [ ] Source health monitoring
- [ ] Historical job lifecycle analytics
- [ ] Daily job review datasets
- [ ] Role-family aggregation
- [ ] Skill trend analytics
- [ ] Search profile effectiveness metrics
- [ ] Search term effectiveness metrics
- [ ] KPI generation
- [ ] Trend analysis
- [ ] Application workflow tracking
- [ ] Application status model
- [ ] API-oriented analytical datasets

Goals:

- Build stable analytical serving datasets
- Support future dashboard visualizations
- Support operational monitoring
- Support historical market analysis
- Support interactive job review workflows
- Support future API consumption

---

## Phase 7 — API & Frontend

- [ ] FastAPI backend
- [ ] REST API endpoints
- [ ] React frontend
- [ ] Interactive dashboard UI
- [ ] Application workflow UI
- [ ] Source monitoring dashboard
- [ ] Authentication concept
- [ ] Local Docker Compose setup

Goals:

- Separate backend and frontend concerns
- Support interactive workflows
- Support future cloud deployment
- Prepare production-oriented architecture

---

## Phase 8 — Cloud & Productionization

- [ ] Azure deployment
- [ ] Managed secrets
- [ ] Scheduling/orchestration
- [ ] Monitoring
- [ ] CI/CD
- [ ] Infrastructure as Code
- [ ] Container orchestration
- [ ] Cost monitoring

Goals:

- Support reliable automated execution
- Improve operational robustness
- Support scalable deployment
- Prepare production-style operations
