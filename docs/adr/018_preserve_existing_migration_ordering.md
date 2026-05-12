# ADR 018: Preserve Existing Migration Ordering

## Status

Accepted

## Context

During early project evolution, database migrations were added incrementally
while the schema model was still evolving rapidly.

This resulted in duplicate migration prefixes:

- 004_make_search_profiles_source_agnostic.sql
- 004_silver_processing_decisions.sql

and:

- 006_job_lifecycle_view.sql
- 006_job_observations_run_level_unique.sql

The migrations are already applied in development environments and referenced
throughout project documentation and discussions.

Renumbering them retroactively would create unnecessary risk and operational
complexity for limited architectural benefit.

## Decision

Existing migration filenames will remain unchanged.

Future migrations must continue with strictly increasing unique prefixes.

Already existing duplicate prefixes are treated as historical artifacts of
early-stage project evolution.

## Consequences

### Positive

- Avoids unnecessary migration churn
- Keeps existing environments stable
- Prevents accidental re-application or ordering confusion
- Documents the historical evolution transparently

### Negative

- Migration numbering is not perfectly sequential
- Repository history contains visible early-stage inconsistencies

## Future Considerations

If the project later adopts a dedicated migration framework
(e.g. Alembic, Flyway, Liquibase),
migration versioning may be formalized and normalized.
