# ADR-015: Use canonical search intent and source capabilities

## Status

Accepted

## Context

The project ingests job postings from heterogeneous real-world sources.

Current implemented sources are:

- Bundesagentur für Arbeit API
- Greenhouse ATS job boards

Future candidates include:

- StepStone
- Workday-based career systems
- Personio
- direct company career pages
- other job platforms

These sources do not expose the same filtering capabilities.

The Bundesagentur connector can apply keyword, location, radius, offer type and pagination server-side.

The Greenhouse connector fetches all jobs for a company board and does not apply the project search term server-side.

However, the project needs comparable search results across sources and should prepare for later CLI, API or GUI based configuration.

## Decision

The project will use a canonical search intent and explicit source capability metadata.

The existing `SearchProfile` and `SearchTerm` dataclasses represent the current canonical search intent.

Every connector receives the same search intent: `SearchProfile + SearchTerm`.

Every connector declares which filters it can apply server-side.

Filters that are not supported server-side are applied locally after fetching where possible.

## Source Capabilities

Each connector declares:

| Capability | Meaning |
|---|---|
| `supports_keyword` | Source can apply keyword search server-side. |
| `supports_location` | Source can apply location search server-side. |
| `supports_radius` | Source can apply radius search server-side. |
| `supports_employment_type` | Source can apply offer or employment type server-side. |
| `supports_remote_filter` | Source can apply remote or hybrid filters server-side. |
| `supports_pagination` | Source supports paginated fetching. |
| `supports_full_fetch` | Source can fetch a complete board or feed. |

## Current Source Classification

| Source | Keyword | Location | Radius | Employment Type | Remote | Pagination | Full Fetch |
|---|---:|---:|---:|---:|---:|---:|---:|
| Bundesagentur für Arbeit | yes | yes | yes | yes | no | yes | no |
| Greenhouse | no | no | no | no | no | no | yes |
| StepStone candidate | yes | yes | likely | unclear | unclear | yes | no |

## Filter Strategy

For each connector:

1. Apply all supported filters server-side.
2. Fetch source-preserving raw records.
3. Apply unsupported but locally feasible filters after fetching.
4. Persist the resulting Bronze records with ingestion lineage.

## Consequences

Connector behavior becomes explicit and reviewable.

The pipeline can support heterogeneous sources without pretending that all APIs behave the same.

The project can later expose the same search intent through hard-coded defaults, CLI arguments, database configuration, API endpoints or a GUI.

The model supports future productization without forcing a rewrite of the connector contract.
