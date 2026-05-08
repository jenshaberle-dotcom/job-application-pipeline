# ADR-009: Use connector-based ingestion for job sources

## Status

Accepted

## Context

The project is intended to ingest job postings from multiple real-world sources. These sources differ in access method, response structure, pagination, identifiers, and data completeness.

The initial implementation started with one working source: the Bundesagentur für Arbeit API. This was useful to validate the database schema, raw ingestion flow, duplicate handling, and search-profile-based ingestion.

As more sources are added, the ingestion logic must not remain coupled to one source implementation.

## Decision

We introduce a connector-based ingestion architecture.

Each job source is implemented as a connector with a shared interface. A connector is responsible for fetching raw job records from one source and returning them in a common internal structure.

The ingestion runner is responsible for orchestration:

- loading active search profiles and search terms
- selecting and executing the connector
- writing raw records to the Bronze layer
- creating and updating ingestion runs
- counting inserted and duplicate records

The repository is responsible for database access.

## Consequences

### Positive

- New sources can be added without rewriting the ingestion runner.
- Source-specific logic is isolated.
- The Bronze layer remains source-preserving.
- The architecture prepares the project for later Silver-layer normalization.
- The implementation becomes easier to test and reason about.

### Negative

- More files and abstractions are introduced earlier than in a simple script.
- The connector interface may need to evolve when more complex sources are added.

## Notes

Skill extraction, skill levels, company normalization, location normalization, and matching are intentionally not implemented inside connectors.

Connectors collect source data.

Silver-layer transformations interpret source data.
