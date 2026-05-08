# Greenhouse API Exploration

## Purpose

This document captures exploratory findings about the Greenhouse public job board APIs.

The goal is to understand:
- response structure
- pagination behavior
- identifier stability
- field variability
- metadata completeness
- HTML handling
- normalization implications for the Silver layer

This document intentionally acts as a bridge between:
- source evaluation
- connector implementation
- canonical model evolution

---

# Example Endpoint Structure

Typical Greenhouse endpoint pattern:

https://boards-api.greenhouse.io/v1/boards/{company}/jobs

Examples:
- https://boards-api.greenhouse.io/v1/boards/openai/jobs
- https://boards-api.greenhouse.io/v1/boards/stripe/jobs
- https://boards-api.greenhouse.io/v1/boards/notion/jobs

---

# Initial Questions

## Pagination

Questions:
- Is pagination offset-based?
- Is pagination cursor-based?
- Are all jobs returned in a single response?
- Are detail endpoints required?

---

## Identifiers

Questions:
- Are IDs globally unique?
- Are IDs only unique per company?
- Are source URLs stable?
- Are deleted jobs removed or marked inactive?

---

## Locations

Questions:
- Single location or multiple locations?
- Remote representation?
- Hybrid representation?
- Country normalization challenges?

---

## HTML Content

Questions:
- Which fields contain HTML?
- Is sanitization required?
- Should Bronze preserve raw HTML?
- Should Silver extract plain text?

---

## Metadata Variability

Questions:
- Which fields are optional?
- Which fields vary between companies?
- Which fields are Greenhouse-specific?
- Which fields map well to the canonical Silver model?

---

# Expected Architectural Learnings

Greenhouse is expected to validate whether the current architecture:
- avoids overfitting to Bundesagentur semantics
- keeps Bronze source-preserving
- keeps Silver source-aware but evolvable
- separates retrieval from interpretation
- can handle incomplete or inconsistent metadata

---

# Planned Next Steps

1. Explore several public Greenhouse endpoints
2. Capture representative raw JSON examples
3. Identify stable fields
4. Identify problematic fields
5. Evaluate pagination behavior
6. Design first Greenhouse Bronze ingestion strategy
7. Design initial Greenhouse-to-Silver transformation approach
