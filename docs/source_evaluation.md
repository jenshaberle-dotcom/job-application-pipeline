# Source Evaluation

## Purpose

The project intentionally evaluates multiple real-world job data sources instead of optimizing only for a single API.

The goal is not only to ingest job postings, but also to understand the architectural, operational and data-quality implications of different source types.

The project therefore intentionally includes:

- structured APIs
- semi-structured APIs
- ATS-based career systems
- HTML-based job pages
- sources with different levels of data quality
- sources with different anti-bot behavior
- sources with different metadata completeness

This evaluation is important to avoid overfitting the architecture to the Bundesagentur für Arbeit API.

Source evaluation should happen before adding complex or operationally risky sources as production connectors.

---

## Evaluation Criteria

| Criterion | Description |
|---|---|
| Access Model | How the source can be accessed, for example public API, public JSON, ATS board, HTML pages or browser-like access |
| Access Complexity | Difficulty of accessing the source reliably |
| Filtering Capability | Degree to which the canonical search intent can be applied server-side |
| Data Structure | Structured vs semi-structured vs HTML |
| Data Completeness | Quality and completeness of available metadata |
| Identifier Quality | Availability and stability of external job identifiers |
| Publication Date Quality | Availability and reliability of publication or freshness metadata |
| Stability | Expected API, endpoint or page stability |
| Anti-Bot Risk | Probability of rate limits, blocking or bot detection |
| Pagination Complexity | Difficulty of traversing result pages |
| Detail Page Requirement | Whether additional page requests are needed |
| Canonical Mapping Difficulty | Difficulty of mapping source data to the Silver model |
| Heartbeat Feasibility | Whether a lightweight source heartbeat can be implemented |
| Maintenance Effort | Expected long-term connector maintenance effort |
| Portfolio Value | Architectural and learning value |
| Legal / Ethical Risk | Terms of service, scraping concerns and responsible-use considerations |

---

## Recommended Evaluation Flow

A new source should move through the following stages:

1. Documentation-only candidate
2. Source analysis
3. Limited technical spike
4. Production connector decision
5. Production connector implementation
6. Dashboard and monitoring integration

Commercial job portals and HTML-based sources should not skip the source analysis and spike stages.

---

## Current Sources

## Bundesagentur für Arbeit API

### Type

Structured public API

### Evaluation Summary

| Criterion | Assessment |
|---|---|
| Access Model | Public API |
| Filtering Capability | Strong |
| Identifier Quality | Stable |
| Publication Date Quality | Exact |
| Pagination Complexity | Low |
| Anti-Bot Risk | Low |
| Heartbeat Feasibility | Good |
| Maintenance Effort | Low |
| Portfolio Value | Medium |
| Legal / Ethical Risk | Low |

### Advantages

- Stable structured responses
- Official public interface
- Good initial Bronze-layer source
- Good for validating ingestion architecture
- Low anti-bot risk
- Reliable pagination
- Strong server-side filtering

### Challenges

- Limited realism compared to modern ATS systems
- German-market-specific structure
- Relatively clean and normalized data
- Lower transformation complexity

### Architectural Value

Useful as the first production-style Bronze ingestion source.

However, the project architecture should not become overly optimized for this source alone.

---

## Greenhouse

### Type

ATS platform

### Evaluation Summary

| Criterion | Assessment |
|---|---|
| Access Model | ATS board |
| Filtering Capability | None in current implementation |
| Identifier Quality | Stable |
| Publication Date Quality | Missing |
| Pagination Complexity | Low for current board usage |
| Anti-Bot Risk | Low |
| Heartbeat Feasibility | Good through board metadata or lightweight board check |
| Maintenance Effort | Medium |
| Portfolio Value | High |
| Legal / Ethical Risk | Low |

### Advantages

- Widely used by technology companies
- More realistic modern recruiting workflow
- Structured but company-specific source behavior
- Good candidate for canonical normalization testing
- Useful for validating full-fetch plus local filtering behavior

### Challenges

- Different company implementations
- Different field availability
- Limited or missing publication metadata
- Requires local filtering for search intent
- Potentially inconsistent metadata quality

### Architectural Value

Greenhouse introduces realistic ATS-style data while remaining manageable for iterative architecture development.

It validates that the connector architecture can handle sources that do not support canonical search intent server-side.

### Decision

Implemented.

---

# Candidate Sources

## StepStone

### Type

Commercial job platform

### Current Status

Initial source analysis in progress. See `docs/source_analysis/stepstone.md`.

### Expected Advantages

- Large job market coverage
- Rich metadata
- Realistic aggregation platform
- High relevance for German job market exploration
- Good test case for commercial portal complexity

### Expected Challenges

- Anti-bot protections
- HTML parsing complexity
- Potential legal restrictions
- Dynamic content loading
- Higher maintenance effort
- Possible consent or blocking behavior
- Unknown identifier stability
- Unknown heartbeat feasibility

### Required Next Step

Complete and review the dedicated StepStone source analysis before implementing a connector.

The analysis should determine:

- access model
- search URL structure
- filter behavior
- pagination model
- identifier stability
- metadata availability
- publication date availability
- blocking or consent behavior
- legal and ethical feasibility
- heartbeat strategy
- whether a limited spike is justified

### Portfolio Value

High, if implemented responsibly and with clear documentation of constraints.

---

## Workday

### Type

Enterprise ATS platform

### Expected Advantages

- Very common in enterprise recruiting
- Highly realistic production scenario
- Good test for normalization boundaries
- Strong portfolio value due to real-world complexity

### Expected Challenges

- Complex page structures
- Dynamic requests
- Difficult navigation flows
- Potential anti-bot protections
- Often inconsistent implementations between companies
- Higher maintenance effort

### Portfolio Value

Very High

---

## Personio

### Type

ATS / company career system

### Expected Advantages

- Common in European companies
- Useful for small and medium-sized company job boards
- Good complement to Greenhouse and Workday

### Expected Challenges

- Company-specific configuration differences
- Potentially inconsistent metadata
- Limited search capabilities
- May require local filtering

### Portfolio Value

Medium to High

---

## Lever

### Type

ATS job board

### Expected Advantages

- Common in technology companies
- Similar architectural category to Greenhouse
- Useful for validating reusable ATS connector patterns

### Expected Challenges

- Board-specific differences
- Limited filtering
- Potential metadata gaps

### Portfolio Value

Medium to High

---

## Company Career Pages

### Type

Direct company websites

### Expected Advantages

- Highly realistic
- Diverse structures
- Good test for connector abstraction
- Good test for canonical modeling
- Can provide original employer-side job postings

### Expected Challenges

- No standardized structure
- High implementation variability
- Potential scraping instability
- Requires source-specific logic
- Requires careful legal and ethical assessment

### Portfolio Value

Very High

---

## Current Direction

The project currently has two implemented source categories:

- search-capable public API
- full-fetch ATS board

The next source expansion should intentionally introduce more architectural complexity than the Bundesagentur für Arbeit API while remaining responsibly scoped.

Before implementing StepStone or similar commercial job portals, the project should first expand source capability documentation and create a dedicated source analysis.

The goal is to validate:

- connector abstraction quality
- Silver-layer boundaries
- canonical model assumptions
- normalization flexibility
- handling of incomplete or inconsistent data
- operational risk assessment
- heartbeat feasibility
- responsible source usage

Learning architectural differences between source types is more important than maximizing ingestion volume.
