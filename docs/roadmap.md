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
- [x] Limited StepStone result-card connector
- [x] Personio XML connector
- [x] Connector-based ingestion architecture
- [x] Source capability abstraction
- [x] Configurable search profiles
- [x] Multi-term search strategy
- [x] Search-term lineage on ingestion runs
- [x] Repository-based persistence
- [x] Ingestion runner orchestration
- [x] Ingestion run tracking
- [x] Ingestion failure diagnostics
- [x] Minimal ingestion logging baseline
- [x] Raw JSON Bronze storage
- [x] Database-level duplicate protection
- [x] Idempotent ingestion behavior
- [x] Local keyword post-filtering
- [x] Job observation tracking
- [x] Observation-based lifecycle preparation

- [~] Multi-source architecture validation
- [~] Observation granularity refinement
- [~] Source-target lineage design
- [~] Controlled Personio Batch 1 source-value validation

- [ ] Explicit source-target lineage implementation
- [ ] Evaluate shared search-intent / term-set model for repeated profile search terms
- [~] Controlled Greenhouse source-target expansion
- [x] First controlled Greenhouse source target activation: Contentful
- [ ] Additional ATS source-target evaluation
- [ ] Additional Personio source-target expansion after Batch 1 decision
- [ ] Softgarden evaluation
- [ ] SmartRecruiters evaluation
- [ ] Workday / SAP SuccessFactors exploration
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
- [x] StepStone source analysis
- [x] Capability-based source abstraction
- [x] Search result connector contract
- [x] Source acquisition scope and source value strategy
- [x] Source target acquisition model
- [x] Source family, source target and source type separation
- [x] Personio source analysis

- [~] Evaluate Personio Batch 1 source value
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
- Avoid uncontrolled or aggressive acquisition patterns

---

## Phase 4 — Silver Layer

- [x] Initial `silver_jobs` table
- [x] Initial Bronze-to-Silver transformation
- [x] Traceability from Silver back to Bronze
- [x] Initial relevance filtering
- [x] Processing decision tracking
- [x] Token-aware relevance matching
- [x] Greenhouse Silver transformation
- [x] Personio Silver transformation
- [x] StepStone Silver transformation
- [x] First Canonicalization Layer
- [x] Normalized title, company and location fields
- [x] Canonical key candidate generation
- [x] Canonicalization backfill script
- [x] Silver source value exploration script

- [~] Lifecycle-oriented Silver preparation
- [~] Source value and overlap exploration

- [ ] Expanded normalization
- [ ] Unified cross-source job representation
- [ ] Location normalization
- [ ] Company normalization
- [ ] Role-family classification
- [ ] Rule-based role family classification implementation
- [ ] Skill extraction
- [ ] Semantic duplicate consolidation
- [ ] Structured metadata extraction

Goals:

- Build stable canonical job representations
- Separate ingestion from analytical datasets
- Prepare lifecycle-aware job intelligence
- Prepare future Gold analytics
- Prepare source-value and overlap analysis without premature canonical merging

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

- [~] Dashboard-oriented Gold views
- [x] Initial source heartbeat view
- [x] New relevant jobs dashboard view
- [x] Source processing summary dashboard view
- [ ] Expanded source health monitoring
- [ ] Dedicated heartbeat/source health architecture
- [ ] Historical job lifecycle analytics
- [ ] Daily job review datasets
- [ ] Role-family aggregation
- [ ] Skill trend analytics
- [ ] Search profile effectiveness metrics
- [ ] Search term effectiveness metrics
- [x] Source value snapshot persistence
- [x] Historical burden baseline analysis
- [x] Cleanup and retention strategy definition
- [x] Historical burden retention dry-run workflow
- [x] Historical archive/export workflow
- [x] Historical burden hot-store removal dry-run review
- [x] Guarded historical burden hot-store removal command
- [ ] Reviewed execution decision for historical burden hot-store removal
- [x] Separate test/transient data cleanup workflow
- [x] Reviewed test/transient cleanup executed locally
- [ ] Source value metrics
- [ ] Source-target quality metrics
- [ ] KPI generation
- [~] Windowed trend analysis
- [x] Read-only source-value window preview
- [x] Source-value trend maturity interpretation
- [x] Trend-eligible metric boundary
- [x] Source-coverage change interpretation boundary
- [x] Controlled source coverage baseline before expansion
- [x] Source-target selection matrix for controlled expansion
- [x] Validate selected Greenhouse board candidates defensively
- [~] Controlled source coverage expansion before serious Gold/dashboard interpretation
- [x] Activate first controlled Greenhouse expansion target after validation
- [x] Document source strategy review boundary after S1D
- [~] Source strategy review before further Greenhouse/Personio/Aggregator expansion
- [x] Aggregator / discovery source family assessment
- [x] Aggregator discovery feasibility matrix and hard-gate definition
- [x] Bounded aggregator discovery candidate evaluation workflow
- [x] Employer candidate and false-negative review workflow
- [x] Employer-origin source candidate validation workflow after S2E review
- [x] Select next active source target after S2F review
- [x] Manually validate Finanz Informatik origin path before connector work
- [ ] Design bounded Finanz Informatik source-target spike with relevance gates
- [ ] Search-intent / term-set normalization cleanup after S1D observation
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
