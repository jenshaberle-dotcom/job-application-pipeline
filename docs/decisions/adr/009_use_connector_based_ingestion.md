# ADR-009: Use connector-based ingestion for job sources

## Status

Accepted

## Context

The project is intended to ingest job postings from multiple real-world sources. These sources differ in access method, response structure, pagination, identifiers, and data completeness.

The initial implementation started with one working source: the Bundesagentur für Arbeit API. This was useful to validate the database schema, raw ingestion flow, duplicate handling, and search-profile-based ingestion.

As more sources are added, the ingestion logic must not remain coupled to one source implementation.

The project therefore needs a clear boundary between:

- source-specific data retrieval
- ingestion orchestration
- Bronze-layer persistence
- later Silver-layer interpretation and normalization

## Decision

We introduce a connector-based ingestion architecture.

Each job source is implemented as a connector with a shared interface. A connector is responsible for fetching raw job records from one source and returning them in a common internal transport structure.

The connector layer is intentionally limited to source access and source-specific transport mapping.

The ingestion runner is responsible for orchestration:

- loading active search profiles and search terms
- executing the configured connector
- writing raw records to the Bronze layer
- creating and updating ingestion runs
- counting inserted and duplicate records

The repository is responsible for database access and persistence behavior.

## Architectural Boundary

Connectors do not perform business-level interpretation.

They should not be responsible for:

- skill extraction
- skill level detection
- company normalization
- location normalization
- duplicate consolidation across sources
- CV-to-job matching
- scoring or recommendation logic

Connectors collect and transport source data.

The Bronze layer remains source-preserving and stores raw source payloads together with ingestion metadata.

Silver-layer transformations will interpret, normalize, enrich, and consolidate source data into a later canonical job model.

## Consequences

### Positive

- New sources can be added without rewriting the ingestion runner.
- Source-specific logic is isolated.
- The Bronze layer remains source-preserving.
- The architecture prepares the project for later Silver-layer normalization.
- The implementation becomes easier to test and reason about.
- Search profiles and search terms can be reused across connector implementations where applicable.
- The project can evolve from a single-source scraper into a multi-source ingestion platform.

### Negative

- More files and abstractions are introduced earlier than in a simple script.
- The connector interface may need to evolve when more complex sources are added.
- Some source-specific differences may only become visible after additional connectors are implemented.
- A future connector registry or factory may become necessary when multiple active sources are supported.

## Notes

The current implementation uses the Bundesagentur für Arbeit connector as the first concrete connector.

Future connectors may include sources such as StepStone, LinkedIn Jobs, Greenhouse-based career pages, Workday-based career pages, or other ATS/career-site integrations.

The current design intentionally keeps the Silver layer out of the connector implementation.
