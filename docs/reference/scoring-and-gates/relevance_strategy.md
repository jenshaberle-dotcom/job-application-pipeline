# Relevance Strategy

## Purpose

This document defines how the project separates raw ingestion from relevant analytical data.

The goal is to build a broad but controlled job-market foundation without flooding Silver and Gold with irrelevant jobs.

The canonical target is **Machine Learning Engineer with strong Data Engineering and Reliability focus**. Data Engineering remains a deliberate bridge and technical focus, not the primary role identity.

## Layer Responsibility

| Layer | Responsibility |
|---|---|
| Bronze | Raw jobs captured within a defined observation scope |
| Silver | Canonicalized jobs considered potentially relevant |
| Gold | Scored, ranked and enriched job intelligence |

## Ingestion Scope

A job is allowed into Bronze only if it belongs to a defined observation scope.

Current scope types:

| Scope Type | Example |
|---|---|
| Regional market | Hannover and realistically commutable surrounding area |
| Remote market | Germany-based remote-friendly roles relevant to the target profile |
| Strategic company | Selected employers or ATS boards |
| Primary role family | Machine Learning Engineering, MLOps, ML/AI Platform |
| Data bridge | Data Engineering, Data Platform, Analytics Engineering |
| Reliability specialization | AI/ML reliability, evaluation, quality and observability |
| Skill cluster | Python, SQL, ML systems, data pipelines, platforms, quality and automation |

## Relevance Criteria

A Bronze job is eligible for Silver if it matches relevant role, task, skill or accessibility signals.

A title alone is neither sufficient nor required. Task content and development direction matter more than exact naming.

### Primary Role Families

- Machine Learning Engineer
- ML Engineer
- MLOps Engineer
- ML Platform Engineer
- AI Platform Engineer
- AI Engineer with engineering, platform, data or reliability substance
- AI/ML Systems Engineer

### Strong Data Engineering Bridge

- Data Engineer
- Data Platform Engineer
- Analytics Engineer with engineering focus
- Cloud Data Engineer
- Data/ML Engineer
- Data Engineer with ML platform, feature, evaluation or production-model proximity

### Strategic Reliability and Quality Adjacencies

- AI Reliability Engineer
- ML Reliability Engineer
- AI Quality Engineer
- Model or Agent Evaluation Engineer
- AI Observability / Assurance roles
- Responsible-AI engineering roles with strong technical implementation content

These labels describe relevant vacancy families. They do not imply that the operator already holds the corresponding formal title or seniority.

### Conditional Adjacent Roles

The following require strong engineering and target-direction evidence:

- Data Scientist with production, deployment, platform or ML-engineering responsibility
- Software Engineer with substantial ML/AI platform responsibility
- Backend/API Engineer with direct data-platform or ML-system relevance
- DevOps or Platform Engineer with explicit MLOps/ML-platform scope

Pure reporting, business-analysis, research-only or generic software roles are not promoted merely because they contain isolated AI, data or Python keywords.

## Skill Clusters

### Machine Learning Engineering

- machine learning
- model development and productionization
- feature engineering or feature platforms
- training and inference pipelines
- model serving
- experiment tracking
- ML platforms
- MLOps

### Reliability, Evaluation and Governance

- model or agent evaluation
- data and model quality
- observability and monitoring
- drift detection and control
- reproducibility
- evidence chains and auditability
- AI assurance or validation
- safe and controlled automation
- testing of ML/AI systems

### Core Data Engineering

- SQL
- Python
- ETL / ELT
- data pipeline
- data warehouse
- data lake / lakehouse
- data platform
- data modeling
- data quality

### Cloud and Platform

- Azure
- AWS
- GCP
- Microsoft Fabric
- Databricks
- Snowflake
- Kubernetes
- Docker

### Orchestration and Transformation

- Airflow
- Dagster
- Prefect
- dbt
- workflow orchestration

### Databases and Storage

- PostgreSQL
- SQL Server
- MongoDB
- Redis
- vector or feature stores when tied to a relevant engineering role

### Software Engineering

- Git
- CI/CD
- APIs
- automated testing
- infrastructure as code
- production diagnostics

## Search Raster Boundary

The active StepStone raster is ML-first and retains Data Engineering bridge terms.

Primary discovery terms include Machine Learning Engineer, ML Engineer, MLOps Engineer, ML Platform Engineer, AI Platform Engineer and AI Engineer.

Data Engineer, Data Platform Engineer and Analytics Engineer remain active because the target profile is data-centric and suitable transition roles may be advertised under these titles.

AI Reliability Engineer and ML Reliability Engineer are strategic probes. ETL, Data Warehouse, Big Data and Python SQL remain matching signals but are no longer standalone primary StepStone searches.

Company-exclusion waves remain limited to search terms with separately validated StepStone `NOT` stability. Search-profile membership alone does not authorize a wave.

## Location, Work Model and Accessibility

A job may be technically relevant but not practically attractive. These criteria are primarily ranking signals rather than universal hard filters.

- Hannover is the geographic center.
- Approximately 30 minutes commute per direction is ideal.
- Up to approximately 45 minutes per direction is generally acceptable.
- Car and public transport are both valid commuting modes.
- Good public-transport access is desirable but not required.
- Hybrid, onsite and fully remote work are all admissible.
- Hybrid wins as a preference when otherwise comparable jobs have similar professional and strategic value.
- A materially stronger ML/AI Reliability development path may outrank a weaker hybrid role.
- Unclear location or office-frequency evidence requires review rather than automatic rejection.

US-only or non-European onsite roles are usually not application candidates, but may remain useful for market and skill-trend analysis when clearly separated from the primary review queue.

## Greenhouse Example

A Greenhouse board may expose all open jobs of a company.

This does not mean every job should be considered relevant.

Example flow:

Greenhouse full fetch  
→ raw jobs captured in Bronze only if the company/profile is in scope  
→ relevance filter checks role, task, skill and accessibility signals  
→ only potentially relevant jobs enter Silver

## Current Diagnostic Finding

Initial Greenhouse diagnostics on the Stripe board showed that naive substring matching is unsafe.

Examples of false positives:

- `bi` matched `billing`
- `api` matched `capital`
- `ai` matched words such as `affairs`

Relevance matching therefore requires token-aware, phrase-aware or structured matching instead of plain substring checks.

## Design Principle

Technical availability is not relevance.

Fetch capability is not ingestion scope.

A matching title is not sufficient proof of suitable work.

Bronze may be broad, but must be bounded.

Silver should be potentially relevant.

Gold should score, rank and explain.

## Boundary to Search Quality and Candidate-Fit Evaluation

The relevance strategy defines whether Bronze records are eligible for Silver normalization.

This is not the same as search-term quality evaluation, false-negative analysis or candidate-fit scoring.

Silver relevance answers:

- Is this raw job potentially relevant enough for canonical normalization?

Search quality later answers:

- Which search terms produce useful jobs?
- Which terms mostly produce noise?
- Which terms uniquely discover relevant employers or roles?
- Where might the active profile miss valuable opportunities?

Candidate-fit scoring later answers:

- How well does this normalized job match the canonical target profile?
- Does the work move the operator toward ML Engineering with Reliability focus?
- Which skills, tasks, role signals or accessibility preferences support or weaken the match?
- Which facts are missing or uncertain?

These later topics remain separate responsibilities under ADR-024 and the operator-approved product contract.
