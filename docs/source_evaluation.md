# Source Evaluation

## Purpose

The project intentionally evaluates multiple real-world job data sources instead of optimizing only for a single API.

The goal is not only to ingest job postings, but also to understand the architectural, operational and data-quality implications of different source types.

## Strategic Source Evaluation Principles

The project does not treat every available source as automatically valuable.

A source must justify its continued use through the additional value it provides compared with its operational, technical and legal or terms-of-service related risk.

The project therefore follows these principles:

1. Prefer official APIs and canonical employer or ATS sources where feasible.
2. Use commercial aggregation platforms primarily as discovery sources.
3. Do not build an alternative public job platform or mirror third-party job advertisements.
4. Do not republish complete third-party job advertisements.
5. Use controlled sampling for sensitive HTML sources.
6. Require explicit acquisition boundaries before expanding pagination or collection depth.
7. Evaluate risky or fragile sources with a Source Value Score before treating them as long-term strategic sources.
8. Downgrade, limit or remove sources whose incremental value does not justify their risk and maintenance cost.

Commercial aggregation platforms can be useful, but their value must be proven.

The long-term goal is not to maximize raw source count. The goal is to build a reliable, explainable and useful personal job-market intelligence system.

## Source Role Strategy

The project distinguishes source roles when evaluating acquisition strategy.

| Source role | Preferred usage | Canonical-source expectation |
|---|---|---|
| Official API source | Primary ingestion and stable market baseline | Strong canonical-source candidate |
| ATS or company-board source | Employer-near acquisition through company or ATS boards | Strong canonical-source candidate |
| Company career page | Employer-origin acquisition when technically and responsibly feasible | Strong canonical-source candidate |
| Commercial aggregator or job portal | Discovery, exploration, source-value comparison and candidate-source discovery | Not canonical by default |

Commercial aggregators can help discover relevant employers, roles and market signals.

They should not be treated as preferred canonical sources when an employer-origin, ATS or official source is available.

This distinction supports the long-term strategy of using commercial platforms defensively while preferring employer-near sources for canonical job evidence.

## Terminology Alignment

Source evaluations use the shared project terminology from `docs/glossary.md`, ADR-022, ADR-026 and ADR-027.

Observed provider-specific structures should be described as source signals and then mapped to canonical project concepts such as source, source target, connector, search intent, result card, detail page, external job ID, Bronze record and canonical job.

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

ATS / company-board source

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
- Employer-near source target model for later canonical-source evaluation

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

Greenhouse boards should be treated as source targets within the Greenhouse source family, not as separate search profiles.

---

# Current Discovery and Candidate Sources

## StepStone

### Type

Commercial job platform

### Current Status

Limited result-card connector implemented. See `docs/source_analysis/stepstone.md`.

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

Do not expand StepStone into broad crawling.

Next steps should focus on:

- source-value evaluation
- search-quality analysis
- controlled source-target lineage
- canonical-source discovery from employer or ATS links where feasible
- maintaining explicit acquisition boundaries
- avoiding detail-page fetching and uncontrolled pagination

### Portfolio Value

High, if kept as a bounded discovery and aggregator source with clear documentation of constraints.

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

The project currently has three implemented source categories:

- search-capable public API
- full-fetch ATS board
- limited commercial aggregator discovery source

The next source expansion should improve source-target lineage and then add controlled ATS or company-board targets before expanding commercial portal acquisition.

Commercial platforms such as StepStone should remain bounded discovery sources unless source-value analysis justifies continued controlled use.

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
