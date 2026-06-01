# Search Intelligence Current State

## Purpose

This document is the primary entry point for understanding the current Search Intelligence subsystem.

It intentionally describes the current architecture rather than historical evolution.

---

## Mission

The project has evolved from a job-search pipeline into a Personal Market Intelligence Platform.

The goal is continuous improvement of:

- Market Understanding
- Discovery Coverage
- Vocabulary Coverage
- Candidate Understanding
- Capability-Gap Visibility

---

## Source Taxonomy

### Source Type

Technical acquisition category.

Examples:

- Official API
- ATS API
- Career Site
- Aggregator
- Structured Job Board

### Source Role

Strategic responsibility within the system.

Examples:

- Company Discovery
- Market Discovery
- Origin Validation
- Ground Truth

See:

- source_taxonomy_and_source_roles.md

---

## Search Intelligence Flow

Exploration & Discovery Sources
↓
Market Evidence
↓
Company Vocabulary
↓
Candidate Intelligence
↓
Search-Term Value
↓
Capability Gap
↓
Employer-Origin Connector Generation
↓
Confirmed Origin Jobs / Better Market Evidence
↓
Future Gold Layer Analytics

---

## Market Evidence

Observed market signals.

Examples:

- Companies
- Roles
- Technologies
- Skill Vocabulary

---

## Company Vocabulary

Observed terminology extracted from market evidence.

Examples:

- analytics
- cloud
- platform
- kafka
- databricks

---

## Candidate Intelligence

Represents:

- Current capability
- Transition assets
- Growth areas

---

## Search-Term Value

Combines:

- Market Evidence
- Vocabulary Signals
- Candidate Direction

Purpose:

Prioritize valuable market terminology.

---

## Capability Gap

Identifies learning opportunities between market demand and current capability.

Examples:

- Spark
- Kafka
- Databricks
- Cloud Data Platforms

---




## Aggregator Novelty Loop

S6B introduces a DB-backed novelty and saturation assessment for bounded aggregator sources.

It reads existing Market Evidence and compares it with known employer-origin candidates and known company vocabulary. The output is a reviewable snapshot that distinguishes unregistered candidate backlog from truly newly observed cycle evidence, and indicates whether the current bounded query is still finding new companies/terms, unresolved candidate reassessment pressure, or mostly saturated repeated evidence.

This layer does not fetch additional pages, mutate profiles, activate sources or write Bronze records.

---
## Employer-Origin Connector Generation

S6A adds a planning layer that turns DB-backed employer-origin candidate gate evidence into a connector-generation plan.

This is the current Ground Truth expansion path. It prepares bounded connector artifact dry runs after source analysis and feasibility gates are satisfied, but it does not activate sources or write Bronze records.

---

## Discovery Metrics

Examples:

- New Companies Discovered
- New Vocabulary Discovered
- Confirmed Origin Jobs
- Connector Generation Plans Ready
- Search-Term Portfolio Growth

---

## Ground Truth Metrics

Examples:

- Relevant Jobs
- Unique Jobs
- Data Quality
- Operational Stability

---

## Related Documents

- source_taxonomy_and_source_roles.md
- search_intelligence_architecture.md
- search_intelligence_terminology.md
- historical_terminology.md
- ../source_analysis/employer_origin_connector_generation_foundation.md
