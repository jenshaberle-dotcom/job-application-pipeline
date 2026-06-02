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
- [x] Add DB-backed historical-burden review batch state
- [x] Guarded historical burden hot-store removal command
- [x] Refactor guarded hot-store removal command to read approved DB batch
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
- [x] Design bounded Finanz Informatik source-target spike with relevance gates
- [x] Implement Finanz Informatik export-first source-target spike
- [x] Probe tiny Finanz Informatik detail pages for selected Hannover candidates
- [x] Add Finanz Informatik incremental uniqueness review workflow
- [x] Prepare disabled Finanz Informatik connector candidate
- [x] Add DB-backed Finanz Informatik activation gate review
- [ ] Manually review Finanz Informatik possible StepStone overlap
- [x] Decide controlled inactive Finanz Informatik source-target registration
- [x] Activate controlled Finanz Informatik Hannover source target
- [ ] Verify Finanz Informatik manual runner output after activation
- [ ] Review Finanz Informatik S2J export artifacts before persistence decision
- [ ] Search-intent / term-set normalization cleanup after S1D observation
- [x] Document employer-origin connector build process
- [x] Add DB-backed employer-origin candidate gate-state model
- [x] Add employer-origin gate agent MVP
- [x] Add detail-evidence and incremental-uniqueness gate agent
- [x] Add employer-origin connector-candidate gate agent
- [x] Add employer-origin connector implementation agent
- [x] Add S4A employer-origin connector artifact generator
- [x] Add employer-origin detail evidence repair agent
- [x] Add employer-origin agent chain driver
- [x] Add employer-origin source lifecycle tracking agent
- [x] Add employer-origin candidate queue agent
- [x] Add employer-origin repair loop safety
- [x] Add employer-origin connector build readiness agent
- [x] Add employer-origin connector registration plan agent
- [x] Add employer-origin connector validation agent
- [x] Add employer-origin final approval gate
- [x] Add employer-origin registration execution plan
- [x] Align S4 gate vocabulary with DB constraints
- [x] Add S4 post-artifact chain and queue orchestration
- [x] Add connector registry foundation for non-activating registration preparation
- [x] Add DB-backed aggregator discovery suppression snapshots for StepStone feedback loop
- [x] Add feed-forward StepStone known-candidate suppression before Bronze persistence
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


## S2O — Export-as-Input Refactoring Audit

- [x] Document remaining export-as-input refactoring scope
- [x] Retire Finanz Informatik legacy S2J/S2K local handoff
- [x] Replace historical-burden hot-store removal file handoff with DB-backed reviewed state
- [ ] Add regression guard against new export-as-input workflows before cloud/CI productionization

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

- S4G: Employer-Origin Approval Workspace for local browser-based gate/action review, explicit implementation/registration approvals and 05A Balanced Intelligence UI alignment.
- S4H: Approval Workspace Candidate Scaling with queue tabs, candidate search and compact 40+-candidate review navigation.


- [x] S5A False Negative Intelligence Foundation
  - DB-backed market evidence model
  - lifecycle-aware StepStone suppression / observation split
  - rule-based false-negative risk engine
  - search-term gap foundation
  - Approval Workspace false-negative risk section


- [x] S5B Search Term Learning and Reassessment Queue
  - DB-backed search-term suggestions
  - reassessment queue for unresolved false-negative risks
  - preview/write agent for converting S5A risks into review work
  - Approval Workspace reassessment tab and compact worklist


## S5C/D Search Intelligence Learning Loop

Track validation outcomes for suggested search terms and derive confidence snapshots before any automatic search-profile mutation is considered.


## S5E Guardrailed Search Strategy Adaptation

Create guardrailed, reviewable search-strategy recommendations from validated search-intelligence signals. Recommendations do not mutate active search profiles yet.


## S5F — Controlled Trial Search Terms

Add bounded, expiring trial terms from guardrailed strategy recommendations without permanent search-profile mutation.


## S5G-A Company Vocabulary Foundation

S5G-A introduces company vocabulary observations as a first step toward company-centered Search Intelligence. Exploration sources are treated primarily as company and vocabulary suppliers; origin sources remain the source of truth for confirmed jobs. The block derives observed company vocabulary from existing market evidence only and does not create new discovery requests, search-profile mutations, Bronze writes, source activations, connector registrations, or scheduler changes.

Initial measurable improvement indicators:

- new vocabulary discovered
- vocabulary per known company
- exploration-source contribution to vocabulary
- later origin confirmation of vocabulary-derived search terms
- search-term portfolio growth per company


## S5G-B Candidate Intelligence Foundation

Candidate Intelligence introduces an explicit candidate profile for Search Intelligence.
It separates current capability from desired career direction so that later vocabulary and search-term value scoring can distinguish between jobs Jens can already do and jobs that support the target transition toward Data Engineering.

Implemented artifacts:

- `candidate_profiles`
- `candidate_skills`
- `src/search_intelligence/candidate_intelligence.py`
- `scripts/run_candidate_profile_agent.py`

Safety boundary: no search-profile mutation, no source activation, no Bronze writes and no scheduler changes.


## S5G-C Search-Term Value Foundation

S5G-C adds the first candidate-specific search-term value layer. It combines company vocabulary observations from S5G-A with the candidate profile from S5G-B. Boundaries remain unchanged: no search-profile mutation, no source activation, no Bronze writes, no scheduler changes.



### S5H — Capability Gap Foundation

Status: implemented in this branch.

S5H adds the first market-signal-based capability-gap layer. It uses the
candidate profile and search-term value scores to identify growth skills such as
Databricks, Spark, Kafka, Cloud Data Platforms or other Data Engineer transition
gaps. This remains a review and learning-prioritization layer only: no
search-profile mutation, no source activation and no Bronze writes.


## Search Intelligence Reconciliation References

The current Search Intelligence reconciliation is documented in:

- docs/architecture/search_intelligence_current_state.md
- docs/architecture/search_intelligence_architecture.md
- docs/architecture/source_taxonomy_and_source_roles.md
- docs/architecture/search_intelligence_terminology.md
- docs/architecture/historical_terminology.md
- docs/planning/search_intelligence_roadmap_alignment.md
- docs/reviews/refactoring_candidate_registry.md



## S6A — Employer-Origin Connector Generation Foundation

S6A introduces a DB-backed connector-generation planning layer for employer-origin source candidates.

The block turns existing candidate and gate evidence into a bounded generation plan:

Discovery Candidate → Source Analysis → Connector Feasibility → Connector Recommendation → Build Plan / Review Artifact.

Boundary: no auto-PR, no source activation, no Bronze writes, no recurring ingestion approval and no CSV/Excel/export artifact as a pipeline input. Human-readable reports remain review outputs only; PostgreSQL stores process state.

Primary artifacts:

- `employer_origin_connector_generation_plans`
- `src/search_intelligence/employer_origin_connector_generation.py`
- `scripts/run_employer_origin_connector_generation_foundation_agent.py`
- `docs/source_analysis/employer_origin_connector_generation_foundation.md`

## S6B — Aggregator Novelty Loop Foundation

S6B adds the DB-backed novelty and saturation layer for bounded exploration sources such as StepStone.

The block evaluates existing Market Evidence and separates:

- unregistered companies vs. known employer-origin candidates
- newly observed companies vs. repeated cycle evidence
- new vocabulary vs. already-known company vocabulary
- newly observed company-term pairs vs. repeated cycle evidence
- unresolved known candidates that should trigger gate reassessment
- saturated queries that repeat already-observed companies and company-term pairs

Boundary: no pagination, no source-limit expansion, no search-profile mutation, no source activation, no Bronze writes and no scheduler changes.

Primary artifacts:

- `aggregator_novelty_snapshots`
- `aggregator_novelty_items`
- `src/search_intelligence/aggregator_novelty.py`
- `scripts/run_aggregator_novelty_loop_agent.py`
- `docs/source_analysis/aggregator_novelty_loop_foundation.md`

## S6C — Approval-Gated Connector Build Agent Foundation

S6C introduces a DB-backed bridge from unresolved high-pressure employer-origin candidates to explicit-approval connector artifact generation. It is designed for candidates like HDI where repeated market evidence exists but direct detail evidence remains incomplete. The block preserves separate final approval, registration and controlled activation gates.


## S6D — Search Intelligence Control Center UI

S6D adds a local DB-backed control surface for the connector lifecycle. It shows active controlled connectors, unresolved candidates, S6C build approval requests and the full discovery-to-approval chain in one place. Approval actions remain token-gated and bounded: connector build approval can create artifacts, while registration and activation remain separate gates.

## S7A Gold Market Coverage & Candidate Lifecycle Foundation

Status: implemented as read-only Gold views.

Purpose: consolidate Search Intelligence signals into dashboard-ready views before further UI polish. This keeps UI rendering aligned with one product-facing interpretation of candidate lifecycle, market coverage, approval backlog, FN pressure and source health.

Next: wire the Search Intelligence Control Center to these Gold views and continue the candidate-to-connector orchestration path.

S7B Gold-backed Control Center: wire the tabbed Control Center to Gold market coverage and candidate lifecycle read models before additional UI polish.

## S7E — Search Intelligence Cycle Audit

S7E documents the current Search Intelligence loop as an end-to-end product cycle instead of a collection of isolated agents.

Primary artifact:

- `docs/source_analysis/search_intelligence_cycle_audit.md`

The audit maps current components, agents, DB read/write boundaries, Gold views, the current manual cycle, a proposed nightly intelligence cycle, scheduler boundaries, risk controls, known gaps and next implementation blocks.

Boundary: documentation only. No source activation, no Bronze writes, no scheduler changes, no connector registration and no search-profile mutation.

Next likely block: S7F Nightly Search Intelligence Orchestrator.



## S7D – Origin Source Discovery Gate Foundation

Origin-source URL discovery is modeled as an explicit DB-backed gate before connector feasibility and connector artifact generation. It evaluates persisted URL evidence only and keeps browsing, activation, registration, Bronze writes and scheduler changes out of scope.

## S7F — Nightly Search Intelligence Orchestrator Foundation

Status: implemented as audit-only foundation.

Purpose: introduce an explicit Search Intelligence cycle coordinator that reads Gold-backed market coverage, candidate lifecycle, approval and origin-source discovery state, derives ordered next actions and can persist an orchestrator run audit. This does not wire a scheduler yet and does not activate sources, register connectors, write Bronze records or mutate search profiles.

Next: review repeated orchestrator runs, then decide whether S7G should expose orchestrator run history in the Control Center or whether S7H should start a bounded scheduler integration design.

## S7G — Orchestrator Attention in Control Center

Status: implemented.

The latest S7F orchestrator attention steps are now exposed through Gold read views and displayed in the Search Intelligence Control Center. This makes `attention_required` cycle output visible in the dashboard and a dedicated Orchestrator tab without running child agents, mutating sources, activating connectors, writing Bronze records or changing scheduler configuration.
