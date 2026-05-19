# Greenhouse Source Analysis

## Purpose

This document evaluates Greenhouse as a real-world ingestion source for the job application pipeline project.

The goal is not only to ingest Greenhouse job postings, but also to evaluate how well the current architecture handles a more realistic ATS-style source compared to the Bundesagentur für Arbeit API.

---

# Source Type

Greenhouse is an Applicant Tracking System (ATS) platform used by many companies for their public job postings.

Examples:
- technology companies
- startups
- SaaS companies
- international organizations

Greenhouse job pages are typically company-specific but follow similar structural patterns.

---

# Architectural Impact

Greenhouse challenges several assumptions shaped by the Bundesagentur für Arbeit API:

- field naming differences
- optional metadata
- multiple locations
- HTML-based content
- inconsistent field completeness
- source-specific semantics
- ATS-specific structures

This source is intentionally selected to validate:

- connector abstraction quality
- Bronze/Silver separation
- canonical normalization flexibility
- future deduplication strategies

---

# Access Pattern

## Current Access Method

Public JSON endpoints.

Typical pattern:

https://boards-api.greenhouse.io/v1/boards/{company}/jobs

Potential detail endpoints may also exist depending on the company implementation.

The current project usage should prefer board-level acquisition and local filtering before considering detail endpoints.

---

# Source Target Model

Greenhouse boards should be treated as source targets within the Greenhouse source family.

Examples:

- `greenhouse:stripe`
- `greenhouse:metronome`
- `greenhouse:teachable`

These source targets should not become separate search profiles.

A stable search profile such as `data_engineering_hannover` can use multiple Greenhouse source targets with the acquisition mode `full_board_with_local_keyword_filter`.

---

# Challenges

## Data Variability

Different companies may expose:

- different departments
- different office structures
- different metadata sections
- different location formats

## HTML Content

Job descriptions may contain:

- HTML formatting
- embedded links
- structured sections
- inconsistent formatting

## Pagination

Pagination behavior must be evaluated.

## Canonical Mapping

The Silver layer must later normalize:

- locations
- departments
- remote information
- employment structures
- metadata sections

without overfitting to Greenhouse-specific semantics.

---

# Bronze Strategy

The Bronze layer should:

- preserve raw JSON responses
- preserve source-specific metadata
- avoid premature normalization
- preserve source identifiers

The connector focuses on:

- retrieval
- transport mapping
- ingestion orchestration compatibility

---

# Silver Strategy

The Silver layer should:

- normalize titles
- normalize locations
- extract company information
- interpret remote/hybrid metadata
- normalize publication timestamps
- extract structured metadata where useful

---

# Portfolio Value

Greenhouse provides significantly more realistic ingestion complexity than the Bundesagentur für Arbeit API while remaining manageable for iterative architecture development.

This makes it a strong intermediate step before more difficult sources such as:

- Workday
- LinkedIn
- StepStone
- custom company career pages
