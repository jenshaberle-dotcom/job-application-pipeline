# Relevance Strategy

## Purpose

This document defines how the project separates raw ingestion from relevant analytical data.

The goal is to build a broad but controlled job market data foundation without flooding Silver and Gold layers with irrelevant jobs.

## Layer Responsibility

| Layer | Responsibility |
|---|---|
| Bronze | Raw jobs captured within a defined ingestion scope |
| Silver | Canonicalized jobs considered potentially relevant |
| Gold | Scored, ranked and enriched job intelligence |

## Ingestion Scope

A job is allowed into Bronze only if it belongs to a defined observation scope.

Current scope types:

| Scope Type | Example |
|---|---|
| Regional market | Hannover and surrounding area |
| Remote market | Remote-friendly roles relevant to the target profile |
| Strategic company | Selected employers or ATS boards |
| Role family | Data Engineering, Analytics Engineering, Data Platform |
| Skill cluster | SQL, Python, ETL, Cloud Data Platforms |

## Relevance Criteria

A Bronze job is eligible for Silver if it matches at least one relevant role or skill signal.

Relevant signals may include:

### Role Families

- Data Engineer
- Analytics Engineer
- Data Platform Engineer
- BI Engineer
- ETL Developer
- Cloud Data Engineer
- Data Analyst with strong engineering focus
- Machine Learning Engineer with platform/data focus

### Skill Clusters

#### Core Data Engineering

- SQL
- Python
- ETL
- ELT
- data pipeline
- data warehouse
- data lake
- data platform

#### Cloud and Platform

- Azure
- AWS
- GCP
- Microsoft Fabric
- Databricks
- Snowflake

#### Orchestration and Transformation

- Airflow
- Dagster
- Prefect
- dbt

#### Databases and Storage

- PostgreSQL
- SQL Server
- MongoDB
- Redis

#### Analytics and BI

- Power BI
- Tableau
- reporting
- dashboarding
- analytics

#### Software Engineering

- Git
- CI/CD
- Docker
- APIs

## Greenhouse Example

A Greenhouse board may expose all open jobs of a company.

This does not mean every job should be considered relevant.

Example:

```text
Greenhouse full fetch
→ raw jobs captured in Bronze only if the company/profile is in scope
→ relevance filter checks role and skill signals
→ only potentially relevant jobs enter Silver
