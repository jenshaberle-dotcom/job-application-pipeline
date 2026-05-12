# Database Tables and Constraints

This document describes the current physical PostgreSQL database model.

It is based on the actual database schema and complements:

```text
docs/diagrams/bronze_data_model.md
```

## Tables

The current schema contains:

| Table | Purpose |
|---|---|
| `search_profiles` | Reusable ingestion profiles. |
| `search_terms` | Multiple active keyword terms per profile. |
| `ingestion_runs` | Operational ingestion lineage. |
| `raw_jobs` | Source-preserving Bronze records. |
| `job_observations` | Repeated sightings of source-local jobs over time. |
| `silver_jobs` | First normalized Silver representation. |

---

# Table: search_profiles

## Purpose

`search_profiles` stores reusable ingestion configuration.

A profile defines source, location, radius, offer type, page size and activation state.

## Columns

| Column | Type | Nullable | Default | Constraint / Index |
|---|---|---:|---|---|
| `id` | `bigint` | no | sequence | Primary key |
| `profile_name` | `text` | no |  | Unique |
| `source_name` | `text` | no |  |  |
| `search_term` | `text` | yes |  | Legacy / nullable |
| `search_location` | `text` | yes |  |  |
| `search_radius_km` | `integer` | yes |  |  |
| `offer_type` | `integer` | yes | `1` |  |
| `page_size` | `integer` | no | `10` |  |
| `is_active` | `boolean` | no | `true` |  |
| `created_at` | `timestamp with time zone` | no | `now()` |  |

## Constraints and Indexes

| Name | Type | Columns | Purpose |
|---|---|---|---|
| `search_profiles_pkey` | Primary key | `id` | Internal technical identifier. |
| `search_profiles_profile_name_key` | Unique constraint | `profile_name` | Allows deterministic execution by profile name. |

## Referenced By

| Referencing Table | Constraint | Relationship |
|---|---|---|
| `search_terms` | `search_terms_search_profile_id_fkey` | One profile has many terms. |
| `ingestion_runs` | `ingestion_runs_search_profile_id_fkey` | One profile has many ingestion runs. |
| `raw_jobs` | `raw_jobs_search_profile_id_fkey` | One profile can produce many raw jobs. |

---

# Table: search_terms

## Purpose

`search_terms` stores multiple keyword terms per search profile.

This avoids duplicating location, radius and source configuration for each role keyword.

## Columns

| Column | Type | Nullable | Default | Constraint / Index |
|---|---|---:|---|---|
| `id` | `bigint` | no | sequence | Primary key |
| `search_profile_id` | `bigint` | no |  | Foreign key |
| `search_term` | `text` | no |  | Unique with profile |
| `is_active` | `boolean` | no | `true` | Indexed |
| `created_at` | `timestamp with time zone` | no | `now()` |  |

## Constraints and Indexes

| Name | Type | Columns | Purpose |
|---|---|---|---|
| `search_terms_pkey` | Primary key | `id` | Internal technical identifier. |
| `search_terms_search_profile_id_fkey` | Foreign key | `search_profile_id` | Prevents orphaned search terms. |
| `search_terms_search_profile_id_search_term_key` | Unique constraint | `search_profile_id`, `search_term` | Prevents duplicate terms within one profile. |
| `idx_search_terms_profile_id` | Index | `search_profile_id` | Speeds up loading terms for a profile. |
| `idx_search_terms_active` | Index | `is_active` | Supports active-term filtering. |

---

# Table: ingestion_runs

## Derived View: source_heartbeat

`source_heartbeat` derives the latest operational status per ingestion source.

It is intended as the first dashboard-oriented monitoring view.

Current fields:

| Field | Meaning |
|---|---|
| `source_name` | Source identifier. |
| `last_ingestion_run_id` | Most recent ingestion run for this source. |
| `last_started_at` | Start timestamp of the latest run. |
| `last_finished_at` | Finish timestamp of the latest run. |
| `last_status` | Raw ingestion run status. |
| `last_total_loaded` | Jobs loaded during the latest run. |
| `last_inserted_count` | Newly inserted raw jobs during the latest run. |
| `last_duplicate_count` | Duplicate jobs skipped during the latest run. |
| `last_error_message` | Error message if the latest run failed. |
| `heartbeat_status` | Dashboard-oriented source status. |

Current heartbeat status values:

| Status | Meaning |
|---|---|
| `healthy` | Latest run completed successfully. |
| `running` | Latest run is currently marked as running. |
| `failed` | Latest run failed. |
| `unknown` | Latest run has an unexpected status. |

Future iterations may add stale detection based on time since the last successful run.

## Purpose

`ingestion_runs` stores one row per ingestion execution.

It provides operational lineage, requested URL information and ingestion statistics.

## Columns

| Column | Type | Nullable | Default | Constraint / Index |
|---|---|---:|---|---|
| `id` | `bigint` | no | sequence | Primary key |
| `source_name` | `text` | no |  |  |
| `search_profile_id` | `bigint` | yes |  | Foreign key |
| `started_at` | `timestamp with time zone` | no | `now()` |  |
| `finished_at` | `timestamp with time zone` | yes |  |  |
| `status` | `text` | no | `'running'` |  |
| `requested_url` | `text` | yes |  |  |
| `total_loaded` | `integer` | no | `0` |  |
| `inserted_count` | `integer` | no | `0` |  |
| `duplicate_count` | `integer` | no | `0` |  |
| `error_message` | `text` | yes |  |  |

## Constraints and Indexes

| Name | Type | Columns | Purpose |
|---|---|---|---|
| `ingestion_runs_pkey` | Primary key | `id` | Internal ingestion run identifier. |
| `ingestion_runs_search_profile_id_fkey` | Foreign key | `search_profile_id` | Links a run to the profile used. |
| `idx_ingestion_runs_search_profile_id` | Index | `search_profile_id` | Supports profile-based run analysis. |

## Referenced By

| Referencing Table | Constraint | Relationship |
|---|---|---|
| `raw_jobs` | `raw_jobs_ingestion_run_id_fkey` | One ingestion run can produce many raw jobs. |

## Derived View: dashboard_new_relevant_jobs

`dashboard_new_relevant_jobs` summarizes newly inserted raw jobs per ingestion run and shows their current Silver relevance processing status.

It is intended as a dashboard-oriented Gold-style view for answering questions such as:

- how many new raw jobs were inserted by a run
- how many of those new jobs are relevant
- how many were skipped by relevance processing
- how many are still unprocessed by the Silver layer

Current fields:

| Field | Meaning |
|---|---|
| `ingestion_run_id` | Ingestion run identifier. |
| `source_name` | Source that produced the ingestion run. |
| `profile_name` | Search profile used for the run. |
| `started_at` | Start timestamp of the ingestion run. |
| `finished_at` | Finish timestamp of the ingestion run. |
| `status` | Ingestion run status. |
| `total_loaded` | Records loaded by the ingestion run after source/local filtering. |
| `inserted_count` | Number of newly inserted raw jobs reported by ingestion. |
| `duplicate_count` | Number of duplicate raw jobs reported by ingestion. |
| `new_raw_jobs` | Number of raw jobs newly linked to this ingestion run. |
| `new_relevant_jobs` | Number of new raw jobs included in Silver processing or already present in `silver_jobs`. |
| `new_skipped_jobs` | Number of new raw jobs skipped by Silver relevance processing. |
| `new_unprocessed_jobs` | Number of new raw jobs without Silver processing decision and without Silver job record. |

Important semantics:

`new_raw_jobs` counts only records newly inserted into `raw_jobs` during the ingestion run.

Repeated observations of already known source-local jobs are not counted as new raw jobs in this view.

This is intentional because duplicate sightings are tracked through `job_observations`, while this view focuses on newly discovered raw job records.

---

# Table: raw_jobs

## Purpose

`raw_jobs` is the source-preserving Bronze table.

It stores original source payloads with minimal transformation.

## Columns

| Column | Type | Nullable | Default | Constraint / Index |
|---|---|---:|---|---|
| `id` | `bigint` | no | sequence | Primary key |
| `source_name` | `text` | no |  | Partial unique with `external_job_id` |
| `source_url` | `text` | no |  |  |
| `external_job_id` | `text` | yes |  | Partial unique with `source_name` |
| `fetched_at` | `timestamp with time zone` | no | `now()` |  |
| `raw_data` | `jsonb` | no |  |  |
| `content_hash` | `text` | yes |  | Future duplicate / change detection |
| `created_at` | `timestamp with time zone` | no | `now()` |  |
| `ingestion_run_id` | `bigint` | yes |  | Foreign key |
| `search_profile_id` | `bigint` | yes |  | Foreign key |

## Constraints and Indexes

| Name | Type | Columns | Purpose |
|---|---|---|---|
| `raw_jobs_pkey` | Primary key | `id` | Internal Bronze record identifier. |
| `idx_raw_jobs_source_external_id` | Partial unique index | `source_name`, `external_job_id` where `external_job_id IS NOT NULL` | Prevents repeated inserts of the same source-local job. |
| `raw_jobs_ingestion_run_id_fkey` | Foreign key | `ingestion_run_id` | Links raw job to producing ingestion run. |
| `raw_jobs_search_profile_id_fkey` | Foreign key | `search_profile_id` | Links raw job to profile context. |
| `idx_raw_jobs_ingestion_run_id` | Index | `ingestion_run_id` | Supports lineage queries. |
| `idx_raw_jobs_search_profile_id` | Index | `search_profile_id` | Supports profile-based analysis. |

## Duplicate Handling

Technical duplicate protection currently uses:

```text
source_name + external_job_id
```

where `external_job_id IS NOT NULL`.

This prevents technical duplicates from the same source.

It does not solve semantic duplicates across sources.

Examples of semantic duplicates:

- the same employer job on Bundesagentur
- the same job on StepStone
- the same job on a company career page
- the same job on an ATS board such as Greenhouse

Semantic deduplication belongs to a later Silver or Gold layer.

---

# Table: job_observations

## Purpose

`job_observations` tracks when a source-local job was observed during ingestion.

It is used to build a historical view of job availability over time.

Unlike `raw_jobs`, which stores one source-preserving Bronze record per technical job identity, `job_observations` stores repeated sightings of the same job across ingestion runs.

This enables future analysis such as:

- first seen date
- last seen date
- number of times observed
- approximate time online
- source activity over time
- job market movement over time

## Columns

| Column | Type | Nullable | Default | Constraint / Index |
|---|---|---:|---|---|
| `id` | `bigint` | no | sequence | Primary key |
| `source_name` | `text` | no |  | Indexed with `external_job_id` |
| `external_job_id` | `text` | yes |  | Indexed with `source_name` |
| `source_url` | `text` | yes |  |  |
| `ingestion_run_id` | `bigint` | yes |  | Foreign key |
| `raw_job_id` | `bigint` | yes |  | Foreign key |
| `observed_at` | `timestamp with time zone` | no | `now()` | Indexed |
| `is_seen` | `boolean` | no | `true` |  |

## Constraints and Indexes

| Name | Type | Columns | Purpose |
|---|---|---|---|
| `job_observations_pkey` | Primary key | `id` | Internal observation identifier. |
| `job_observations_ingestion_run_id_fkey` | Foreign key | `ingestion_run_id` | Links an observation to the ingestion run in which it occurred. |
| `job_observations_raw_job_id_fkey` | Foreign key | `raw_job_id` | Links an observation to the canonical raw job record when available. |
| `idx_job_observations_source_external_id` | Index | `source_name`, `external_job_id` | Supports source-local job history analysis. |
| `idx_job_observations_observed_at` | Index | `observed_at` | Supports time-based observation analysis. |
| `idx_job_observations_ingestion_run_id` | Index | `ingestion_run_id` | Supports ingestion-run lineage queries. |
| `idx_job_observations_raw_job_id` | Index | `raw_job_id` | Supports raw-job based observation history. |

## Relationship to raw_jobs

`raw_jobs` stores the source-preserving Bronze record.

`job_observations` stores each time that job was observed during ingestion.

For newly inserted raw jobs, `raw_job_id` is known immediately.

For duplicate jobs, the ingestion logic looks up the existing `raw_jobs.id` and stores it in `job_observations.raw_job_id`.

This keeps repeated sightings linked to the same raw job identity.

## Current Limitation

The table currently records positive sightings only.

It does not yet record explicit disappearance events.

A job can currently be considered "last seen" based on the maximum `observed_at` value for a given `source_name` and `external_job_id`.

Future iterations may add explicit not-seen tracking or run-level source snapshots to detect removals more precisely.

## Derived View: job_lifecycle

`job_lifecycle` derives basic lifecycle metrics from `job_observations`.

Current fields:

| Field | Meaning |
|---|---|
| `source_name` | Source that provided the job. |
| `external_job_id` | Source-local job identifier. |
| `first_seen_at` | First time this pipeline observed the job. |
| `last_seen_at` | Last time this pipeline observed the job. |
| `runs_seen` | Number of distinct ingestion runs in which the job was observed. |
| `observed_days` | Full days between `first_seen_at` and `last_seen_at`. |

Important semantic distinction:

`first_seen_at` is not necessarily the original publication date.

`observed_days` is not necessarily the full online duration of a job posting.

These metrics describe the observation window of this pipeline.

True publication or availability duration requires additional source metadata such as:

- `publication_date`
- `first_published`
- `posted_at`
- `application_deadline`

---

# Table: silver_jobs

## Purpose

`silver_jobs` is the first canonical representation derived from Bronze records.

It stores normalized fields for analysis while preserving traceability to the original raw record.

## Columns

| Column | Type | Nullable | Default | Constraint / Index |
|---|---|---:|---|---|
| `id` | `bigint` | no | sequence | Primary key |
| `raw_job_id` | `bigint` | no |  | Unique foreign key |
| `source_name` | `text` | no |  | Indexed |
| `external_job_id` | `text` | yes |  | Indexed |
| `source_url` | `text` | yes |  |  |
| `title` | `text` | yes |  |  |
| `company_name` | `text` | yes |  | Indexed |
| `city` | `text` | yes |  | Indexed |
| `postal_code` | `text` | yes |  |  |
| `country` | `text` | yes |  |  |
| `publication_date` | `date` | yes |  | Indexed |
| `normalized_at` | `timestamp with time zone` | no | `now()` |  |
| `created_at` | `timestamp with time zone` | no | `now()` |  |
| `updated_at` | `timestamp with time zone` | no | `now()` |  |

## Constraints and Indexes

| Name | Type | Columns | Purpose |
|---|---|---|---|
| `silver_jobs_pkey` | Primary key | `id` | Internal Silver identifier. |
| `silver_jobs_raw_job_id_key` | Unique constraint | `raw_job_id` | Ensures at most one Silver row per Bronze row. |
| `silver_jobs_raw_job_id_fkey` | Foreign key | `raw_job_id` | Preserves traceability to the raw source record. |
| `idx_silver_jobs_source_name` | Index | `source_name` | Supports source-based analysis. |
| `idx_silver_jobs_external_job_id` | Index | `external_job_id` | Supports source-local lookup. |
| `idx_silver_jobs_company_name` | Index | `company_name` | Supports employer analysis. |
| `idx_silver_jobs_city` | Index | `city` | Supports location analysis. |
| `idx_silver_jobs_publication_date` | Index | `publication_date` | Supports time-based analysis. |

---

# Current Design Boundaries

## Source of Truth

`raw_jobs.raw_data` remains the source of truth.

`silver_jobs` is derived data.

## Technical Duplicate Protection

Implemented at Bronze level using:

```text
source_name + external_job_id
```

## Cross-Source Deduplication

Not implemented yet.

Future semantic matching should consider:

- normalized title
- normalized company name
- normalized location
- source URL domain
- publication date window
- content hash
- description similarity
- original employer career page if available

## Filter Application Tracking

Not persisted in the database yet.

The next step introduces source capability metadata in code.

Potential future fields:

| Field | Meaning |
|---|---|
| `server_filter_applied` | Filter was applied by source/API/query. |
| `local_filter_applied` | Filter was applied after fetching. |
| `unsupported_filter_ignored` | Filter could not be applied reliably. |
| `filter_notes` | Human-readable explanation. |
