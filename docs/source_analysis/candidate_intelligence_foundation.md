# Candidate Intelligence Foundation

Status: implemented in S5G-B.

## Purpose

S5G-B introduces the first explicit candidate profile used by Search Intelligence.
It separates two dimensions that must not be mixed:

- current capability: what the candidate can credibly do today
- career direction: where the candidate wants the search strategy to move

This matters because a high current fit does not automatically mean a high-value job for the target direction. Requirements Engineering may be a strong current capability, while Data Engineering is the intended target role.

## Boundary

This block is read-only with respect to the pipeline:

- no search-profile mutation
- no source activation
- no connector registration
- no scheduler changes
- no Bronze writes

The profile is a Search Intelligence input, not an ingestion control surface.

## Initial Profile

The initial profile is intentionally curated rather than parsed automatically from a CV.
It starts with `Jens Career Transition`, target role `Data Engineer`, version `v1`.

The first skill model includes:

- current strengths: Requirements Engineering, Product Ownership, Systems Engineering, Stakeholder Management
- transition assets: SQL, Python, PostgreSQL, Data Modeling, ETL Pipelines, Azure
- growth areas: Databricks, Spark, Kafka, Cloud Data Platforms

## Why this comes after Company Vocabulary

S5G-A showed that exploration evidence can produce company vocabulary, but it also produced noisy terms. Candidate Intelligence is needed before vocabulary can become search-term value. A term is not universally valuable; it is valuable for a target candidate profile and career direction.

## Follow-up

The next block should combine company vocabulary with candidate intelligence to produce Search-Term Value signals. That later block can rank terms like `analytics`, `platform`, `cloud`, or `requirements` by both market signal and fit to the Data Engineer target direction.
