# ADR 018: Normalize Migration Prefixes

## Status

Accepted

## Context

During early project evolution, database migrations were added incrementally while the schema model was still evolving rapidly.

This resulted in duplicate migration prefixes.

Examples included:

- `004_make_search_profiles_source_agnostic.sql`
- `004_silver_processing_decisions.sql`

and:

- `006_job_lifecycle_view.sql`
- `006_job_observations_run_level_unique.sql`

The duplicate prefixes were historical artifacts of early-stage project development.

They were not intentionally designed as a long-term migration strategy.

The project is still in an early local-development stage and does not yet use a dedicated migration framework such as Alembic, Flyway or Liquibase.

As more dashboard views, source integrations and future migration files are added, duplicated prefixes would create unnecessary confusion.

## Decision

The project will normalize migration filenames to use unique, strictly increasing numeric prefixes.

The existing migration files are renamed once before further source expansion.

Future migrations must continue with unique numeric prefixes.

The normalized sequence is:

- `001_bronze_ingestion_model.sql`
- `002_search_terms_model.sql`
- `003_silver_jobs_model.sql`
- `004_make_search_profiles_source_agnostic.sql`
- `005_silver_processing_decisions.sql`
- `006_job_observations.sql`
- `007_job_observations_run_level_unique.sql`
- `008_job_lifecycle_view.sql`
- `009_source_heartbeat_view.sql`
- `010_dashboard_new_relevant_jobs_view.sql`
- `011_dashboard_source_processing_summary_view.sql`

## Consequences

### Positive

- Removes confusing duplicate migration prefixes
- Makes migration ordering easier to understand
- Improves repository readability before additional source expansion
- Reduces recurring documentation ambiguity
- Creates a clean baseline for future migration files

### Negative

- Changes historical migration filenames
- Requires documentation updates
- Existing local environments may already have applied the old filenames manually
- A future migration framework would still need a formal migration history table

## Operational Notes

This project currently applies migrations manually during local development.

Because no dedicated migration framework tracks applied filenames, renaming these files does not automatically re-run or roll back database changes.

Existing local databases should be treated as development databases.

Fresh environments should apply the normalized migration sequence.

## Future Considerations

If the project later adopts a dedicated migration framework, migration versioning should be formalized and tracked explicitly.
