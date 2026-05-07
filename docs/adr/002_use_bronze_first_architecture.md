# ADR-002 — Use Bronze-First Data Architecture

## Status

Accepted

---

## Context

The project integrates multiple external job market sources with potentially inconsistent and evolving data structures.

At the beginning of the project, the final normalized target schema is unknown because:
- additional data sources are not yet integrated
- field structures vary between providers
- some sources may expose richer detail data
- universal vs source-specific fields are not yet identified

Early normalization would risk overfitting the architecture to a single source.

---

## Decision

Adopt a Bronze-first ingestion architecture.

The Bronze layer stores:
- raw API responses
- raw source payloads
- ingestion metadata
- source identifiers
- search profile references
- ingestion run references

Raw source data is intentionally preserved before normalization.

Normalization and semantic processing are deferred to later Silver and Gold layers.

---

## Consequences

### Positive

- source-agnostic ingestion
- easier onboarding of new sources
- preservation of original payloads
- easier debugging and traceability
- reduced risk of premature schema design
- improved architectural flexibility

### Negative

- larger storage requirements
- temporary redundancy in raw data
- delayed normalization
- more downstream processing complexity
