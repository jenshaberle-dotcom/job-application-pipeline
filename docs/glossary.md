# Project Glossary

This glossary explains recurring technical terms, abbreviations, and architectural concepts used throughout the project.

The goal is not to provide academic definitions, but practical project-oriented explanations.

## Shared source and layer terminology

The project uses one shared terminology across all sources and all lakehouse-style layers.

Source-specific differences are documented as mappings, capabilities or source-specific metadata. They should not create separate project vocabularies per connector.

Core terms:

| Term | Meaning |
|---|---|
| Source | External system or website family that can provide job data. |
| Source family | Logical provider or platform family, for example `personio`, `greenhouse`, `stepstone` or `bundesagentur_fuer_arbeit`. |
| Source type | Strategic classification of a source family or target, for example official API, ATS board, company career page or commercial aggregator. |
| Connector | Project code responsible for accessing one source and converting source data into project records. |
| Search intent | Source-independent description of what the project wants to find, for example role keywords and location. |
| Source query | Source-specific translation of a search intent into URL parameters, API parameters or form inputs. |
| Source target | Concrete acquisition target inside a source family, for example a Greenhouse board, Personio tenant, company career page or controlled discovery query. Source targets are not search profiles. |
| Source capability | Documented property of a source, for example search support, stable identifiers, pagination or detail availability. |
| Source role | Architectural role of a source, for example official API source, ATS/company-board source, discovery source, aggregator source or fallback source. |
| Acquisition mode | Description of how a source target is queried, for example API search, company-board fetch, limited probe or controlled sampling. |
| Acquisition policy | Operational and responsible-use boundaries for acquisition, for example page caps, detail-page restrictions, timeouts or fail-closed URL rules. |
| Canonical source candidate | Source or source target that may be suitable as preferred evidence for a canonical job identity. |
| Raw source payload | Source-preserving response material, for example HTML, JSON or text received from a source. |
| Result card | One search-result item shown by a source before opening a detail page. |
| Detail page | Source page or endpoint containing a fuller job description. |
| External job ID | Identifier assigned by the source or extracted from source URLs or source markup. |
| Bronze record | Persisted source-preserving record, including provenance and raw/source-specific payload. |
| Canonical job | Source-independent Silver-layer representation of a job posting. |
| Source-specific metadata | Fields that are useful but not part of the canonical model. |

Layer rules:

- Bronze preserves source evidence.
- Silver normalizes into canonical project terminology.
- Gold uses business-facing metrics and should not depend on source-specific structures.

Related terminology and contracts:

- [ADR-022](adr/022_define_shared_source_and_layer_terminology.md)
- [ADR-023](adr/023_define_search_result_connector_contract.md)
- [ADR-026](adr/026_define_source_acquisition_scope_and_canonical_source_strategy.md)
- [ADR-027](adr/027_define_source_target_acquisition_model.md)
- [ADR-028](adr/028_separate_source_family_target_and_type.md)
- [Search Result Connector Contract](data_sources/search_result_connector_contract.md)

Additional search-result connector contract terms:

| Term | Meaning |
|---|---|
| Source result ID | Source-specific result-card identifier before it is validated as a stable external job ID. |
| Detail URL | Source URL pointing to a fuller job detail page. |
| Raw data | Code-level field used by `RawJobRecord` for source-specific payload. |
| Raw payload | Architecture term for source-preserving data; currently stored as `raw_data`. |

---

# A

## ADR — Architecture Decision Record

A lightweight document used to capture important architectural or technical decisions.

An ADR typically explains:

* the problem or context
* the decision that was made
* why the decision was chosen
* advantages and disadvantages
* long-term implications

In this project, ADRs are used to document the architectural evolution of the platform.

Example:

* ADR-009 documents the connector-based ingestion architecture.
* ADR-010 documents the canonical Silver-layer model.

---

## API — Application Programming Interface

A structured interface that allows systems to exchange data programmatically.

Examples in this project:

* Bundesagentur für Arbeit API
* Greenhouse Job Board API

Compared to HTML scraping, APIs usually provide more stable and structured data.

---

## ATS — Applicant Tracking System

Software used by companies to manage recruiting and job applications.

Examples:

* Greenhouse
* Workday
* Lever

ATS systems are important in this project because they represent realistic real-world job data sources.

---

# B

## Bronze Layer

The raw ingestion layer of the platform.

The Bronze layer stores source-preserving raw data exactly as it was received from the source.

The Bronze layer intentionally avoids:

* normalization
* business interpretation
* deduplication across sources
* enrichment
* skill extraction

The goal is to preserve traceability and prevent data loss.

Example table:

* `raw_jobs`

---

# C

## Canonical Model

A normalized internal representation of data that is independent of the original source.

In this project:

* different job sources may expose different field names and structures
* the Silver layer transforms them into a common canonical representation

Example:

* Bundesagentur and Greenhouse may represent locations differently
* the canonical model later provides one consistent internal structure

---

## Connector

A source-specific ingestion component.

A connector is responsible for:

* retrieving source data
* handling source-specific access patterns
* mapping source data into transport structures
* preserving source semantics

A connector is NOT responsible for:

* business interpretation
* normalization
* skill extraction
* cross-source deduplication

Examples:

* `BundesagenturConnector`
* `GreenhouseConnector`
* `PersonioConnector`
* `StepStoneConnector`

---

## CV — Curriculum Vitae

A résumé or professional profile.

The project later plans to support CV-to-job matching using semantic similarity and structured skill extraction.

---

# D

## Data Platform

A broader architectural concept describing systems that ingest, process, transform, normalize, analyze, and serve data.

The project evolved from a simple ingestion script toward a lightweight data platform architecture.

---


## Deep Ocean Intelligence

The project's visual identity for dashboards, diagrams, presentations, README visuals and future frontend work.

The style emphasizes calm technical competence, dark ocean-like surfaces, controlled cyan/blue accents, source governance, operational observability and analytical depth.

It is documented in:

- [Design and Platform Identity](design/README.md)
- [ADR-031](adr/031_define_platform_visual_identity.md)

## Design System

A reusable set of visual and communication rules for project assets.

In this project, the design system is intentionally lightweight. It defines colors, layer mappings, visual rules, dashboard terminology and source-risk visualization boundaries.

It is not meant to turn documentation into marketing material. It is meant to make architecture and source-quality decisions easier to understand.

## Deduplication

The process of identifying and handling duplicate records.

In this project, duplicates may occur because:

* multiple platforms publish the same job
* companies repost positions
* the same source republishes data

Current Bronze-layer deduplication uses database-level constraints.

Future Silver-layer deduplication may become semantic and cross-source-aware.

---

# E

## Embeddings

Numerical vector representations of text generated by machine learning models.

Embeddings can later be used for:

* semantic similarity
* CV-to-job matching
* recommendation systems
* skill similarity

Currently planned for future project phases.

---

# G

## Gold Layer

The analytics and business-consumption layer.

The Gold layer later derives:

* dashboards
* KPIs
* scoring
* recommendations
* matching results
* analytics

Gold builds on normalized Silver data.

---

## Greenhouse

An Applicant Tracking System (ATS) platform.

Greenhouse is implemented as an ATS board source because it introduces more realistic ingestion complexity than the Bundesagentur für Arbeit API while remaining manageable.

The project uses Greenhouse to validate:

* connector abstraction
* Silver-layer flexibility
* canonical normalization assumptions
* multi-source ingestion architecture

---

# H

## HTML Scraping

Extracting information from HTML web pages instead of structured APIs.

Compared to APIs, HTML scraping is usually:

* less stable
* more fragile
* harder to maintain
* more sensitive to layout changes

The project intentionally evaluates both API-based and HTML-based sources.

---

# I

## Idempotency

A property where running the same operation multiple times produces the same result.

In this project:

* ingestion should not create duplicate records when rerun
* Bronze ingestion uses database constraints to support idempotent behavior

---

## Ingestion

The process of retrieving and storing data from external systems.

In this project, ingestion includes:

* source access
* pagination handling
* transport mapping
* Bronze-layer persistence
* ingestion tracking

---

# J

## JSON — JavaScript Object Notation

A structured text format commonly used for APIs.

Most APIs explored in this project return JSON responses.

Example:

* Greenhouse job board responses
* Bundesagentur API responses

---

# K

## KPI — Key Performance Indicator

A measurable metric used to evaluate system or business performance.

Future examples in the project:

* source effectiveness
* search-term effectiveness
* matching quality
* ingestion statistics

---

# L

## LLM — Large Language Model

A machine learning model trained on large amounts of text.

Potential future use cases:

* semantic enrichment
* skill extraction
* classification
* matching support

---

# M

## Medallion Architecture

A layered data architecture pattern typically consisting of:

* Bronze
* Silver
* Gold

The project architecture increasingly follows this pattern.

---

## Metadata

Additional structured information about a record.

Examples:

* publication dates
* departments
* offices
* remote indicators
* source identifiers

Metadata quality varies strongly between sources.

---

## Multi-Source Ingestion

The ability to ingest and process data from multiple independent external systems.

This is one of the central architectural goals of the project.

---

# N

## Normalization

The process of transforming inconsistent source data into a stable and comparable structure.

Examples:

* location normalization
* company normalization
* title normalization
* canonical field mapping

Normalization primarily belongs to the Silver layer.

---

# O

## Orchestration

The coordination of multiple processing steps.

In this project, orchestration includes:

* loading search profiles
* executing connectors
* triggering ingestion runs
* persisting Bronze records
* running Silver transformations

Example:

* `JobIngestionRunner`

---

# P

## Pagination

A mechanism used by APIs or websites to split large result sets into multiple pages.

Pagination handling is an important connector responsibility.

Different sources may use:

* page-based pagination
* offset-based pagination
* cursor-based pagination

---

## PostgreSQL

The primary relational database used by the project.

Reasons for selection:

* strong SQL support
* transactional reliability
* JSON support
* good local development experience
* realistic production relevance

---

# R

## Raw Data

Unmodified source data.

The project intentionally preserves raw source payloads in the Bronze layer.

This supports:

* traceability
* debugging
* replayability
* future reinterpretation

---

## Repository Pattern

A software design pattern used to separate persistence logic from business logic.

In this project:

* repositories manage database interaction
* runners orchestrate workflows
* connectors retrieve source data

Examples:

* `JobIngestionRepository`
* `SilverJobRepository`

---

# S

## Schema

The structural definition of data.

Examples:

* Bronze database schema
* Silver canonical schema
* migration definitions

---

## Semantic Matching

Matching based on meaning rather than exact keywords.

Future project goal:

* compare CVs and job postings semantically
* use embeddings or language models

---

## Silver Layer

The normalized and interpreted transformation layer.

Silver transforms Bronze raw data into a stable canonical representation.

Responsibilities include:

* normalization
* interpretation
* enrichment
* canonical mapping
* preparation for analytics and matching

Example table:

* `silver_jobs`

---

## Source-Preserving

An architectural principle meaning:

* original source structure is retained
* raw payloads remain accessible
* premature normalization is avoided

This is one of the core principles of the Bronze layer.

---

# T

## Traceability

The ability to trace transformed data back to its original source.

In this project:

* Silver records reference Bronze records
* Bronze preserves original payloads

This improves:

* debugging
* explainability
* reproducibility

---

## Transformation

The process of converting data from one structure into another.

Example:

* Bronze raw records -> Silver canonical jobs

---

# W

## Workday

A widely used enterprise ATS platform.

Workday is considered a future high-complexity source candidate because:

* implementations differ strongly between companies
* data structures are inconsistent
* navigation is often complex
* anti-bot protections may exist

Workday is expected to become a future architectural stress test for the platform.

---

# WS

## WSL — Windows Subsystem for Linux

A compatibility layer that allows Linux environments to run directly on Windows.

The project uses WSL2 as the local development environment.

This enables:

* Linux tooling
* Docker integration
* Python development
* realistic local development workflows
