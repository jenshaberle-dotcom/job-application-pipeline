# Role Family Classification Concept

## Purpose

This document describes the planned role family classification layer for job postings.

The goal is to enrich normalized job data with a transparent, explainable and testable role classification that supports dashboard analytics, matching and job market intelligence.

## Motivation

Job titles from different sources are heterogeneous.

Examples:

- Data Engineer
- Senior Data Platform Engineer
- Product Owner Data Platform
- Requirements Engineer Software
- Agile Requirements Manager
- BI Consultant
- Machine Learning Engineer
- System Engineer Vehicle Motion

Simple source-level aggregation is not enough to understand the actual role landscape.

A role family classification layer should make it possible to answer questions such as:

- how many relevant jobs belong to Data Engineering
- how many jobs are closer to Product Ownership
- how many jobs match Requirements Engineering
- which sources produce which role families
- how the role distribution changes over time

## Initial Role Families

The initial role taxonomy should be small, pragmatic and aligned with the user's target roles.

Proposed initial role families:

| Role Family | Description |
|---|---|
| `data_engineering` | Data engineering, data platforms, pipelines, ETL/ELT, analytics engineering |
| `data_analytics_bi` | BI, reporting, analytics, dashboards, business intelligence |
| `data_science_ml` | Data science, machine learning, AI, model development |
| `product_ownership` | Product Owner, Product Manager, product-focused platform ownership |
| `requirements_engineering` | Requirements engineering, requirements management, business analysis |
| `agile_coaching` | Scrum Master, Agile Coach, ways of working |
| `software_engineering` | Software development roles without stronger data/platform classification |
| `systems_engineering` | Systems engineering, mechatronic/software system roles |
| `devops_platform_engineering` | DevOps, cloud platform, infrastructure, CI/CD, SRE |
| `other_unknown` | Jobs that cannot be classified confidently |

## Classification Scope

The first implementation should be rule-based.

It should not claim to be a perfect semantic AI classifier.

Initial inputs:

- normalized job title from `silver_jobs`
- source name
- company name
- optionally location
- later: description text
- later: extracted skills

Initial outputs:

- primary role family
- optional secondary role family
- classification method
- confidence score
- matched keywords or rules

## Rule-Based First Approach

A rule-based first approach is intentionally chosen because it is:

- transparent
- explainable
- easy to test
- easy to debug
- suitable for portfolio review
- extendable toward semantic or ML-based approaches later

Example rules:

| Pattern | Candidate Role Family |
|---|---|
| `data engineer`, `etl`, `pipeline`, `analytics engineer` | `data_engineering` |
| `business intelligence`, `bi`, `reporting`, `dashboard` | `data_analytics_bi` |
| `machine learning`, `ml engineer`, `data scientist`, `ai engineer` | `data_science_ml` |
| `product owner`, `product manager` | `product_ownership` |
| `requirements engineer`, `requirements manager`, `business analyst` | `requirements_engineering` |
| `scrum master`, `agile coach`, `ways of working` | `agile_coaching` |
| `software engineer`, `developer`, `backend`, `frontend` | `software_engineering` |
| `system engineer`, `systems engineer`, `system development` | `systems_engineering` |
| `devops`, `platform engineer`, `cloud engineer`, `sre`, `ci/cd` | `devops_platform_engineering` |

## Ambiguity Handling

Some jobs may match multiple role families.

Examples:

- Product Owner Data Platform
- Requirements Engineer Software
- Agile Requirements Manager
- BI Data Engineer
- Platform Product Owner

The classifier should therefore support:

- primary role family
- secondary role family
- confidence score
- matched rule trace
- `other_unknown` fallback

Ambiguous jobs should not be silently forced into a single category without traceability.

## Candidate Data Model

A future implementation may use a dedicated classification table instead of mutating `silver_jobs` directly.

Candidate table:

### job_role_classifications

| Field | Meaning |
|---|---|
| `id` | Classification identifier |
| `silver_job_id` | Referenced Silver job |
| `primary_role_family` | Main assigned role family |
| `secondary_role_family` | Optional secondary role family |
| `classification_method` | For example `rule_based_v1` |
| `confidence_score` | Numeric confidence score |
| `matched_terms` | Keywords or rule identifiers that caused the classification |
| `created_at` | Classification timestamp |

## Dashboard Usage

Potential dashboard widgets:

- relevant jobs by role family
- new relevant jobs by role family
- role family distribution by source
- role family distribution over time
- ambiguous or unknown jobs requiring review
- target-role coverage by source

## Quality Control

The classifier should be evaluated with manual spot checks.

Useful quality checks:

- examples per role family
- unknown rate
- ambiguous rate
- false positive examples
- false negative examples
- classification distribution by source
- rule hit statistics

## Future Extensions

Possible later improvements:

- weighted rule scoring
- description-based classification
- skill-based classification
- embedding-based similarity
- LLM-assisted classification
- manual feedback loop
- role taxonomy versioning

## Current Decision

The project should treat role family classification as a separate semantic enrichment feature.

It should not be implemented as a simple dashboard-only view.

A dashboard should consume classification results after they have been produced by a transparent and testable classification step.
