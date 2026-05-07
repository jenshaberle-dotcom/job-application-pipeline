# ADR-004 — Use Search Profile Based Ingestion

## Status

Accepted

---

## Context

The project aims to ingest broad and realistic job market datasets instead of narrowly filtered search results.

Using a single hardcoded search query would:
- reduce market coverage
- hide potentially relevant jobs
- tightly couple ingestion logic to application code
- limit future experimentation

Additionally:
- different search strategies may overlap
- search effectiveness should later become measurable
- multiple semantic domains may require different search terms

---

## Decision

Introduce configurable search profiles and search terms.

Architecture:
- `search_profiles`
    - defines search strategy metadata
- `search_terms`
    - contains multiple search terms per profile

The ingestion process dynamically loads active search profiles and terms from the database.

---

## Consequences

### Positive

- broader market coverage
- configurable ingestion behavior
- easier experimentation
- future analytics on search effectiveness
- scalable ingestion architecture
- improved separation between configuration and code

### Negative

- increased ingestion complexity
- more duplicate overlap between search terms
- larger ingestion volumes
