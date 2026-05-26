# Dashboard Vision

## Purpose

The dashboard is intended to turn the job pipeline into an interactive job market intelligence and application workflow system.

It should not only show ingested jobs, but also support operational monitoring, candidate review, application tracking and market trend analysis.

## Target Architecture

Preferred future architecture:

PostgreSQL  
→ stable database views / Gold datasets  
→ FastAPI backend  
→ React frontend  
→ local Docker setup  
→ optional later cloud deployment

## Dashboard Areas

Future dashboard maturity should distinguish operational monitoring from semantic job enrichment:

- source health should combine ingestion runs and dedicated heartbeat checks
- role distribution should be based on explicit role family classification

### 1. Source Health Monitoring

Goal:

Show whether each source is active and working.

Current state:

Source health is initially derived from ingestion run data.

Future state:

Source health should combine productive ingestion runs with dedicated lightweight heartbeat checks.

Example indicators:

- green: last run successful
- yellow: last run completed with warnings or low result count
- red: last run failed
- grey: source inactive

Current data basis:

- `dashboard_source_processing_summary`
- `dashboard_new_relevant_jobs`
- `source_heartbeat`
- `ingestion_runs`
- `search_profiles`

Future data basis:

- dedicated heartbeat checks
- source health snapshots
- source configuration metadata

Suggested metrics:

- last run time
- last run status
- jobs loaded
- new jobs inserted
- duplicates skipped
- error type
- error stage
- error message

### 2. Daily Job Review

Goal:

Show the most relevant jobs for manual review.

Potential features:

- top 5 daily job candidates
- relevance reason
- source
- company
- location
- publication date
- first seen date
- application status

Possible statuses:

- `new`
- `ai_prepared`
- `reviewed`
- `applied`
- `rejected`
- `archived`

Potential data basis:

- `silver_jobs`
- `silver_processing_decisions`
- future scoring tables
- future `job_application_status`

### 3. Application Workflow

Goal:

Allow manual tracking of the application process.

Required future table:

- `job_application_status`

Potential fields:

- `id`
- `silver_job_id`
- `status`
- `notes`
- `status_changed_at`
- `created_at`
- `updated_at`

The dashboard should allow manual updates later through an API endpoint.

### 4. New Relevant Jobs Since Last Run

Goal:

Show how many new potentially relevant jobs were found since the last ingestion run.

Current data basis:

- `dashboard_new_relevant_jobs`

Underlying tables:

- `ingestion_runs`
- `raw_jobs`
- `silver_jobs`
- `silver_processing_decisions`

Supported metrics:

- new raw jobs per ingestion run
- new relevant jobs per ingestion run
- skipped jobs per ingestion run
- unprocessed new jobs per ingestion run

Potential visualization:

- bar chart by source
- daily count
- run-over-run comparison

### 5. Historical Job Availability

Goal:

Show how the observed job market develops over time.

Potential data basis:

- `job_observations`
- `job_lifecycle` view

Potential metrics:

- first seen
- last seen
- runs seen
- observed days
- estimated online duration if source publication metadata exists

Important distinction:

`first_seen_at` means first observed by this pipeline.

It does not necessarily mean the original publication date.

### 6. Source and Role Distribution

Goal:

Show how many relevant jobs come from each source family, source target, source type and role family.

Current state:

Source distribution can be derived from existing ingestion and Silver data.

Future state:

Role distribution should be based on explicit role family classification instead of raw title keyword aggregation.

Potential visualization:

- stacked bar chart by source family or source target
- role family as stacked segments
- Pareto-style chart for source contribution

Possible role families:

- Data Engineer
- Analytics Engineer
- Data Analyst
- Data Scientist
- Platform / Backend
- Machine Learning
- Other

Required future data concept:

- `role_family`

This should be derived in Silver or Gold, not only in the frontend.

### 7. Skill and Requirement Heatmaps

Goal:

Show which skills and tools appear most often across relevant jobs.

Potential dimensions:

- skill
- source
- company
- role family
- city / region
- remote policy
- publication month
- first seen month

Example questions:

- Which skills are most common in relevant jobs?
- Which sources contain the most Data Engineering roles?
- Which companies frequently post platform/data roles?
- How does demand for SQL, Python, Azure or Snowflake change over time?

Required future data concept:

- `job_skill_matches`

## API Preparation

Potential future endpoints:

- `GET /dashboard/source-health`
- `GET /dashboard/top-jobs`
- `GET /dashboard/new-jobs-by-run`
- `GET /dashboard/job-lifecycle`
- `GET /dashboard/source-role-distribution`
- `GET /dashboard/skill-heatmap`
- `GET /jobs`
- `PATCH /jobs/{id}/application-status`

## Implementation Strategy

The dashboard should not be implemented directly against raw ingestion tables.

Preferred sequence:

1. Stabilize lifecycle and relevance semantics.
2. Define Gold/database views for dashboard use cases.
3. Add FastAPI read endpoints.
4. Add application status write endpoint.
5. Build React frontend.
6. Add local Docker Compose setup.
7. Evaluate cloud deployment later.

## Current Decision

Visualization is planned but intentionally deferred.

The current project should prepare the data model and documentation first, so the future UI can be built on stable concepts rather than temporary ingestion internals.
