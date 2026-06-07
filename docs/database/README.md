# Database Documentation

Status: current schema reference entry point
Scope: DOC-001H database map and constraint/navigation surface

## Purpose

This directory documents the PostgreSQL model used by the Job Application
Pipeline.

The database is not only a storage detail. It is the product backbone for:

- source-safe Bronze ingestion,
- Silver normalization and relevance decisions,
- employer-origin candidates and gates,
- Search Intelligence learning loops,
- connector-build approvals,
- orchestrator/action audit trails,
- Gold/read-model views used by the Control Center.

## Read this first

| Document | Role |
|---|---|
| `docs/database/schema_overview.md` | Domain-level overview of current tables and views. |
| `docs/database/schema_relationships.md` | Mermaid relationship diagrams for the main table networks. |
| `docs/database/tables.md` | Older detailed core-table documentation; useful, but incomplete for the current Search Intelligence schema. |
| `docs/operations/db_migration_tracking.md` | Migration execution and schema-migration tracking rules. |

## Important status note

`docs/database/tables.md` started as the physical schema detail page for the
Bronze/Silver core. It is still useful for early tables, but it is not a complete inventory of the current schema.

DOC-001H therefore introduces a higher-level schema overview and relationship
map first. Detailed per-table documentation can be regenerated or expanded later
from the migration/database introspection path.

## Maintainer rule

When a migration adds a new table, view, constraint vocabulary, or important
relationship, update either:

1. `schema_overview.md`, if it changes a domain area or lifecycle, or
2. `schema_relationships.md`, if it changes the graph between tables, or
3. `tables.md`, if detailed column/constraint documentation is being maintained
   for that table family.
