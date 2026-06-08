# ADR-014: Document database schema and constraints

## Status

Accepted

## Context

The project has evolved from a single-source ingestion experiment into a multi-source job market intelligence pipeline.

The database is no longer only an implementation detail. It represents important architectural concepts:

- reusable search profiles
- multiple active search terms per profile
- ingestion run lineage
- source-preserving Bronze records
- first canonical Silver records
- technical duplicate protection
- traceability from Silver back to Bronze

The existing `docs/archive/diagrams/bronze_data_model.md` documents the model visually, but the project also needs granular table and constraint documentation.

## Decision

The project will document the physical database model explicitly.

The documentation includes:

- tables
- columns
- primary keys
- foreign keys
- unique constraints
- indexes
- relationship cardinalities
- data quality rationale
- current limitations
- planned extensions

The detailed documentation is stored in:

- `docs/archive/diagrams/bronze_data_model.md`
- `docs/reference/database/tables.md`

## Consequences

Schema decisions become easier to review.

Future migrations should update the database documentation in the same change set.

The documentation can later support CLI parameters, GUI configuration, Silver modeling, Gold modeling and semantic deduplication.

## DOC-001I note

The former Bronze/Silver diagram page was physically archived to
`docs/archive/diagrams/bronze_data_model.md`. The current schema relationship
map is `docs/reference/database/schema_relationships.md`.
