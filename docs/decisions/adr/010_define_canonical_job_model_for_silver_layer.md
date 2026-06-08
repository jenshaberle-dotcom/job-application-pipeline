# ADR-010: Define a canonical job model for the Silver layer

## Status

Accepted

## Context

The Bronze layer stores raw job records in a source-preserving way. This is intentional because different job sources provide different fields, structures, identifiers, metadata, and levels of completeness.

However, raw source data is not suitable for reliable analytics, matching, deduplication, or comparison across sources.

The project therefore needs a later Silver layer that transforms raw job postings into a canonical job representation.

This canonical model will provide a stable internal structure independent of the original source.

---

## Decision

We introduce a canonical job model in the Silver layer.

The Silver layer is responsible for interpreting and normalizing raw Bronze records into a consistent structure.

The first implementation introduces an initial `silver_jobs` table and a source-aware Bronze-to-Silver transformation step.

The canonical job model currently focuses on:

- job title
- company name
- location
- publication date
- source references
- ingestion traceability

The model will evolve incrementally as additional sources are integrated.

---

## Architectural Boundary

Bronze stores what the source provided.

Silver interprets what the data means.

Gold later derives metrics, scores, recommendations, and dashboards from Silver data.

Connectors must not implement Silver-layer logic.

The Silver layer may initially contain source-aware transformations, but should evolve toward a stable canonical representation independent of any single source.

---

## Consequences

### Positive

- Job postings from different sources become comparable.
- Analytics can be built on stable normalized data.
- Matching logic can rely on a consistent representation.
- Source-specific quirks remain isolated in Bronze.
- The architecture supports later cross-source deduplication.
- The project follows a clear Bronze/Silver/Gold separation.

### Negative

- Additional transformation logic is required.
- Some source fields may not map cleanly to the canonical model.
- Missing values must be handled explicitly.
- The canonical model may evolve as new sources are added.
- Premature over-modeling must be avoided.

---

## Notes

The canonical model should start pragmatic and evolve with real data.

The first Silver-layer implementation is based on the Bundesagentur für Arbeit source, but the model must not become tightly coupled to this source alone.

Future sources such as Greenhouse, Workday, StepStone, or company career pages are expected to introduce:
- different field structures
- inconsistent metadata
- HTML content
- incomplete records
- source-specific semantics

The Silver layer should preserve traceability back to the original Bronze record.
