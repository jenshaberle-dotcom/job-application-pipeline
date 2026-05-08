# ADR-010: Define a canonical job model for the Silver layer

## Status

Proposed

## Context

The Bronze layer stores raw job records in a source-preserving way. This is intentional because different job sources provide different fields, structures, identifiers, metadata, and levels of completeness.

However, raw source data is not suitable for reliable analytics, matching, deduplication, or comparison across sources.

The project therefore needs a later Silver layer that transforms raw job postings into a canonical job representation.

This canonical model will provide a stable internal structure independent of the original source.

## Decision

We will introduce a canonical job model in the Silver layer.

The Silver layer will be responsible for interpreting and normalizing raw Bronze records into a consistent structure.

The canonical job model should represent fields such as:

- job title
- company name
- location
- remote/hybrid information
- employment type
- seniority level
- required skills
- optional skills
- source references
- original source identifiers
- publication date
- ingestion metadata

The canonical model will not replace the Bronze layer.

Bronze remains the immutable source-preserving layer. Silver provides the interpreted and normalized representation used for analytics, deduplication, enrichment, and matching.

## Architectural Boundary

Bronze stores what the source provided.

Silver interprets what the data means.

Gold later derives metrics, scores, recommendations, and dashboards from Silver data.

Connectors must not implement Silver-layer logic.

## Consequences

### Positive

- Job postings from different sources become comparable.
- Analytics can be built on stable, normalized data.
- Matching logic can rely on a consistent representation.
- Source-specific quirks remain isolated in Bronze.
- The project can support cross-source deduplication.
- The architecture follows a clear Bronze/Silver/Gold separation.

### Negative

- Additional transformation logic is required.
- Some source fields may not map cleanly to the canonical model.
- Missing values must be handled explicitly.
- The canonical model may evolve as new sources are added.
- Premature over-modeling must be avoided.

## Notes

The canonical model should start pragmatic and evolve with real data.

The first Silver-layer implementation may be based on the Bundesagentur für Arbeit data source, but the model must not be designed only around this source. Future sources are expected to include more difficult real-world inputs such as HTML pages, ATS-based career sites, incomplete postings, differently named fields, and source-specific metadata.

Not every field needs to be normalized immediately. The first implementation should focus on fields that are required for deduplication, search analysis, and CV-to-job matching.

The Silver layer should preserve traceability back to the original Bronze record.
