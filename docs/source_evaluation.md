# Source Evaluation

## Purpose

The project intentionally evaluates multiple real-world job data sources instead of optimizing only for a single API.

The goal is not only to ingest job postings, but also to understand the architectural, operational, and data-quality implications of different source types.

The project therefore intentionally includes:

- structured APIs
- semi-structured APIs
- ATS-based career systems
- HTML-based job pages
- sources with different levels of data quality
- sources with different anti-bot behavior
- sources with different metadata completeness

This evaluation is important to avoid overfitting the architecture to the Bundesagentur für Arbeit API.

---

# Evaluation Criteria

| Criterion | Description |
|---|---|
| Access Complexity | Difficulty of accessing the source |
| Data Structure | Structured vs semi-structured vs HTML |
| Data Completeness | Quality and completeness of metadata |
| Stability | Expected API/page stability |
| Anti-Bot Risk | Probability of rate limits or blocking |
| Pagination Complexity | Difficulty of traversing result pages |
| Detail Page Requirement | Whether additional page requests are needed |
| Canonical Mapping Difficulty | Difficulty of mapping to the Silver model |
| Portfolio Value | Architectural and learning value |
| Legal / Ethical Risk | Terms of service and scraping concerns |

---

# Current Sources

## Bundesagentur für Arbeit API

### Type

Structured public API

### Advantages

- Stable structured responses
- Official public interface
- Good initial Bronze-layer source
- Good for validating ingestion architecture
- Low anti-bot risk
- Reliable pagination

### Challenges

- Limited realism compared to modern ATS systems
- German-market-specific structure
- Relatively clean and normalized data
- Lower transformation complexity

### Architectural Value

Useful as the first production-style Bronze ingestion source.

However, the project architecture should not become overly optimized for this source alone.

---

# Candidate Sources

## Greenhouse

### Type

ATS platform

### Expected Advantages

- Widely used by technology companies
- More realistic modern recruiting workflows
- Structured but company-specific variations
- Good candidate for canonical normalization testing

### Expected Challenges

- Different company implementations
- Different field availability
- Potential pagination differences
- Potentially inconsistent metadata quality

### Portfolio Value

High

### Decision

Selected as the next connector candidate.

Greenhouse introduces more realistic ATS-style data while remaining manageable for iterative architecture development.

---

## Workday

### Type

Enterprise ATS platform

### Expected Advantages

- Very common in enterprise recruiting
- Highly realistic production scenario
- Good test for normalization boundaries

### Expected Challenges

- Complex page structures
- Dynamic requests
- Difficult navigation flows
- Potential anti-bot protections
- Often inconsistent implementations between companies

### Portfolio Value

Very High

---

## StepStone

### Type

Commercial job platform

### Expected Advantages

- Large job market coverage
- Rich metadata
- Real-world aggregation platform

### Expected Challenges

- Anti-bot protections
- HTML parsing complexity
- Potential legal restrictions
- Dynamic content loading
- Higher maintenance effort

### Portfolio Value

High

---

## Company Career Pages

### Type

Direct company websites

### Expected Advantages

- Highly realistic
- Diverse structures
- Good test for connector abstraction
- Good test for canonical modeling

### Expected Challenges

- No standardized structure
- High implementation variability
- Potential scraping instability
- Requires source-specific logic

### Portfolio Value

Very High

---

# Current Direction

Greenhouse has been selected as the next connector candidate.

The next source should intentionally introduce more architectural complexity than the Bundesagentur für Arbeit API.

The goal is to validate:

- connector abstraction quality
- Silver-layer boundaries
- canonical model assumptions
- normalization flexibility
- handling of incomplete or inconsistent data

The Greenhouse connector does not need to be production-grade immediately.

Learning architectural differences between source types is more important than maximizing ingestion volume.
