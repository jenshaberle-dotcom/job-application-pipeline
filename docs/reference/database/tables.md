# Database Tables and Constraints

Status: legacy core-table detail / partial current reference
Scope: Bronze/Silver core tables; not a complete Search Intelligence schema inventory

## DOC-001H status note

This page is still useful for detailed early core-table descriptions, but it is
not a complete description of the current database anymore.

Read these first for the current schema map:

- `docs/reference/database/README.md`
- `docs/reference/database/schema_overview.md`
- `docs/reference/database/schema_relationships.md`


This document describes the current physical PostgreSQL database model.

It is based on the actual database schema and complements:

```text
docs/archive/diagrams/bronze_data_model.md (historical); current relationship map: docs/reference/database/schema_relationships.md
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
| `source_value_snapshots` | Historical source-value metrics for source families, targets and operational source names. |
| `silver_processing_decisions` | Silver relevance processing decisions for raw jobs. |
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

It provides operational lineage, requested URL information, search-term lineage and ingestion statistics.

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
| `search_term_id` | `bigint` | yes |  | Foreign key to `search_terms`. |
| `search_term` | `text` | yes |  | Historical term snapshot used by the run. |
| `total_loaded` | `integer` | no | `0` |  |
| `inserted_count` | `integer` | no | `0` |  |
| `duplicate_count` | `integer` | no | `0` |  |
| `error_message` | `text` | yes |  | Human-readable failure detail. |
| `error_type` | `text` | yes |  | Classified failure type for operational diagnostics. |
| `error_stage` | `text` | yes |  | Pipeline stage where a failure occurred. |

## Constraints and Indexes

| Name | Type | Columns | Purpose |
|---|---|---|---|
| `ingestion_runs_pkey` | Primary key | `id` | Internal ingestion run identifier. |
| `ingestion_runs_search_profile_id_fkey` | Foreign key | `search_profile_id` | Links a run to the profile used. |
| `idx_ingestion_runs_search_profile_id` | Index | `search_profile_id` | Supports profile-based run analysis. |
| `idx_ingestion_runs_search_term_id` | Index | `search_term_id` | Supports search-term quality analysis. |
| `idx_ingestion_runs_search_term` | Index | `search_term` | Supports historical term-snapshot analysis. |
| `idx_ingestion_runs_status_error_type` | Index | `status`, `error_type` | Supports failed-run diagnostics by failure category. |
| `idx_ingestion_runs_error_stage` | Partial index | `error_stage` where `status = 'failed'` | Supports failed-run diagnostics by pipeline stage. |

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

## Derived View: dashboard_source_processing_summary

`dashboard_source_processing_summary` summarizes ingestion and relevance processing metrics per source.

It is intended as a dashboard-oriented Gold-style view for comparing source behavior and processing status across sources.

Current fields:

| Field | Meaning |
|---|---|
| `source_name` | Source identifier. |
| `ingestion_run_count` | Number of ingestion runs for the source. |
| `successful_run_count` | Number of successful ingestion runs for the source. |
| `failed_run_count` | Number of failed ingestion runs for the source. |
| `latest_ingestion_at` | Latest ingestion start timestamp for the source. |
| `latest_successful_ingestion_at` | Latest successful ingestion finish timestamp for the source. |
| `total_loaded_jobs` | Total records loaded by ingestion runs for the source. |
| `total_inserted_jobs` | Total newly inserted raw jobs reported by ingestion. |
| `total_duplicate_jobs` | Total duplicate jobs reported by ingestion. |
| `total_new_raw_jobs` | Total raw jobs newly linked to ingestion runs for the source. |
| `total_new_relevant_jobs` | Total new raw jobs considered relevant for Silver. |
| `total_new_skipped_jobs` | Total new raw jobs skipped by Silver relevance processing. |
| `total_new_unprocessed_jobs` | Total new raw jobs without Silver processing decision and without Silver job record. |
| `has_unprocessed_jobs` | Indicates whether the source still has unprocessed new raw jobs. |
| `duplicate_rate` | Duplicate share among all loaded jobs. |
| `new_relevance_rate` | Relevance share among newly inserted raw jobs. |

Important semantics:

This view aggregates source-level processing metrics from `dashboard_new_relevant_jobs`.

It compares source behavior, but it does not replace source health monitoring.

Operational source health should later combine ingestion runs with dedicated heartbeat checks.

Note: `ingestion_runs.error_type` and `ingestion_runs.error_stage` provide the first persisted diagnostics surface for failed productive ingestion runs. They do not replace a future dedicated heartbeat or source-health model.

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

# Table: source_value_snapshots

## Purpose

`source_value_snapshots` stores historical source-value metrics for source families, concrete source targets and operational source names.

It is used to persist source evaluation evidence over time instead of relying only on ad-hoc script output or one-time manual interpretation.

The table supports later lifecycle decisions such as limiting, pausing, deprecating or continuing a source, but it does not make those decisions automatically.

## Columns

| Column | Type | Nullable | Default | Constraint / Index |
|---|---|---:|---|---|
| `id` | `bigint` | no | sequence | Primary key |
| `snapshot_at` | `timestamp with time zone` | no | `now()` | Indexed with source fields |
| `snapshot_reason` | `text` | no | `'manual'` | Describes why the snapshot was created. |
| `source_name` | `text` | no |  | Indexed with `snapshot_at` |
| `source_family` | `text` | no |  | Indexed with `snapshot_at` |
| `source_target` | `text` | yes |  | Indexed |
| `source_type` | `text` | yes |  | Strategic source type. |
| `evaluation_window_started_at` | `timestamp with time zone` | yes |  | Future explicit window start. |
| `evaluation_window_finished_at` | `timestamp with time zone` | yes |  | Future explicit window end. |
| `ingestion_runs` | `integer` | no | `0` |  |
| `successful_runs` | `integer` | no | `0` |  |
| `failed_runs` | `integer` | no | `0` |  |
| `fetched_jobs_before_filter` | `integer` | yes |  | Future metric for source records before local filtering. |
| `matched_jobs_after_filter` | `integer` | no | `0` | Current matched/loaded run semantics. |
| `inserted_jobs` | `integer` | no | `0` | Newly inserted Bronze jobs. |
| `duplicate_jobs` | `integer` | no | `0` | Duplicate records reported by ingestion. |
| `raw_jobs` | `integer` | no | `0` | Current raw jobs for the source. |
| `silver_jobs` | `integer` | no | `0` | Current Silver jobs for the source. |
| `distinct_companies` | `integer` | no | `0` | Diversity signal. |
| `distinct_candidate_keys` | `integer` | no | `0` | Canonical-candidate diversity signal. |
| `rows_in_duplicate_candidate_groups` | `integer` | no | `0` | Rows belonging to same-source candidate duplicate groups. |
| `rows_in_cross_source_candidate_groups` | `integer` | no | `0` | Rows belonging to cross-source candidate groups. |
| `cross_source_candidate_keys` | `integer` | no | `0` | Candidate keys observed across sources. |
| `title_completeness_pct` | `numeric(5,2)` | yes |  | Data quality metric. |
| `company_completeness_pct` | `numeric(5,2)` | yes |  | Data quality metric. |
| `location_completeness_pct` | `numeric(5,2)` | yes |  | Data quality metric. |
| `publication_date_completeness_pct` | `numeric(5,2)` | yes |  | Data quality metric. |
| `matched_rate_pct` | `numeric(5,2)` | yes |  | Search-intent fit metric. |
| `duplicate_rate_pct` | `numeric(5,2)` | yes |  | Technical duplicate burden metric. |
| `failure_rate_pct` | `numeric(5,2)` | yes |  | Operational reliability metric. |
| `source_value_score` | `numeric(6,2)` | yes |  | Future score; not authoritative by itself. |
| `lifecycle_state` | `text` | yes |  | Future lifecycle state; indexed. |
| `recommendation` | `text` | yes |  | Future human-review recommendation. |
| `notes` | `text` | yes |  | Human-readable interpretation notes. |
| `metrics` | `jsonb` | no | `'{}'::jsonb` | Extensible metric payload. |
| `created_at` | `timestamp with time zone` | no | `now()` |  |

## Constraints and Indexes

| Name | Type | Columns | Purpose |
|---|---|---|---|
| `source_value_snapshots_pkey` | Primary key | `id` | Internal snapshot identifier. |
| `idx_source_value_snapshots_source_name_snapshot_at` | Index | `source_name`, `snapshot_at DESC` | Supports source-local snapshot history. |
| `idx_source_value_snapshots_source_family_snapshot_at` | Index | `source_family`, `snapshot_at DESC` | Supports source-family level trend analysis. |
| `idx_source_value_snapshots_source_target` | Index | `source_target` | Supports source-target evaluation. |
| `idx_source_value_snapshots_lifecycle_state` | Index | `lifecycle_state` | Supports lifecycle-state filtering. |

## Interpretation Boundary

Initial snapshots currently use all locally available history unless an explicit evaluation window is provided by future tooling.

All-time values are useful as a baseline, but they can be distorted by historical broad-match runs, old search-term semantics, exploration spikes and local test data.

Lifecycle decisions should therefore not rely on a single all-time snapshot. Future 24h, 7d and 30d windows should be used for trend-aware source lifecycle evaluation.

---

# Table: silver_processing_decisions

## Purpose

`silver_processing_decisions` stores why a raw job was included in or skipped by Silver processing.

It preserves relevance-processing evidence without forcing every raw job into `silver_jobs`.

This keeps Silver transformation transparent and supports later analysis of false positives, false negatives and search-term quality.

## Columns

| Column | Type | Nullable | Default | Constraint / Index |
|---|---|---:|---|---|
| `id` | `bigint` | no | sequence | Primary key |
| `raw_job_id` | `bigint` | no |  | Unique foreign key |
| `decision` | `text` | no |  | Indexed |
| `reason` | `text` | yes |  |  |
| `role_matches` | `jsonb` | yes |  |  |
| `skill_matches` | `jsonb` | yes |  |  |
| `accessibility_matches` | `jsonb` | yes |  |  |
| `decided_at` | `timestamp with time zone` | no | `now()` |  |

## Constraints and Indexes

| Name | Type | Columns | Purpose |
|---|---|---|---|
| `silver_processing_decisions_pkey` | Primary key | `id` | Internal processing-decision identifier. |
| `silver_processing_decisions_raw_job_id_key` | Unique constraint | `raw_job_id` | Ensures at most one processing decision per raw job. |
| `silver_processing_decisions_raw_job_id_fkey` | Foreign key | `raw_job_id` | Preserves traceability to the raw source record. |
| `idx_silver_processing_decisions_decision` | Index | `decision` | Supports relevance-processing analysis. |

## Relationship to silver_jobs

`silver_processing_decisions` and `silver_jobs` serve different purposes.

- `silver_processing_decisions` records whether and why a raw job was included or skipped.
- `silver_jobs` stores the normalized Silver representation for included jobs.

A raw job may have a processing decision without having a Silver job row.

---

# Table: silver_jobs

## Purpose

`silver_jobs` is the first canonical representation derived from Bronze records.

It stores normalized fields for analysis while preserving traceability to the original raw record.

`silver_jobs` now also acts as the first canonicalization candidate layer.

The table no longer represents only a normalized projection of Bronze fields.

It now additionally stores first-stage canonicalization metadata and overlap-preparation fields.

Important boundary:

`silver_jobs` does not yet represent final cross-source canonical job entities.

Cross-source duplicate resolution, canonical source selection and semantic job clustering remain future responsibilities.

Current canonicalization support includes:

- normalized text fields
- canonical candidate status
- canonical source typing
- canonical key candidates for overlap analysis
- preparation for future source-value evaluation

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
| `normalized_title` | `text` | yes |  | Indexed |
| `normalized_company_name` | `text` | yes |  | Indexed |
| `normalized_location` | `text` | yes |  |  |
| `canonical_status` | `text` | yes |  | Indexed |
| `canonical_source_type` | `text` | yes |  |  |
| `canonical_key_candidate` | `text` | yes |  | Indexed |
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
| `idx_silver_jobs_normalized_company_name` | Index | `normalized_company_name` | Supports canonical employer matching preparation. |
| `idx_silver_jobs_normalized_title` | Index | `normalized_title` | Supports canonical title matching preparation. |
| `idx_silver_jobs_canonical_status` | Index | `canonical_status` | Supports canonicalization state analysis. |
| `idx_silver_jobs_canonical_key_candidate` | Index | `canonical_key_candidate` | Supports duplicate-candidate and overlap analysis. |

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

## Filter Application and Source-Target Lineage

Per-run filter application details are not fully persisted in the database yet.

Source capability metadata exists in code and documentation, while explicit source-target lineage remains future work.

Potential future fields:

| Field | Meaning |
|---|---|
| `server_filter_applied` | Filter was applied by source/API/query. |
| `local_filter_applied` | Filter was applied after fetching. |
| `unsupported_filter_ignored` | Filter could not be applied reliably. |
| `filter_notes` | Human-readable explanation. |


## historical_burden_review_batches

DB-backed review batches for historical-burden hot-store removal decisions.

Generated Markdown/JSON files may summarize these batches for human review, but execution must use approved DB state.

Key fields:

- `id` — review batch identifier
- `status` — `proposed`, `reviewed`, `approved`, `executed` or `cancelled`
- `review_reason` — human-readable reason for the batch
- `retention_track` — retention policy track represented by the batch
- `candidate_count`, `eligible_for_removal_count`, `blocked_or_non_actionable_count` — review counters
- `source_counts`, `burden_category_counts`, `review_status_counts` — JSONB summaries
- `metadata` — non-operational context for audit/review

## historical_burden_review_items

Per-raw-job review items belonging to a historical-burden review batch.

`raw_job_id` is intentionally stored as a value rather than as a foreign key to `raw_jobs`, so the review item remains auditable after a later approved hot-store removal.

Key fields:

- `batch_id` — owning review batch
- `raw_job_id` — raw job identifier snapshot
- `source_name`, `external_job_id`, `source_url`, `fetched_at` — source evidence snapshot
- `burden_category`, `retention_track`, `review_status` — review classification
- `eligible_for_future_removal` — candidate flag; not an execution approval
- `execution_status` — later execution result state
- `item_snapshot` — JSONB item snapshot for auditability

---

## aggregator_discovery_suppression_batches

DB-backed review batches for aggregator-discovery suppression decisions.

The table supports the StepStone feedback loop where aggregator-origin company
signals are compared against known employer-origin candidates.

Key fields:

- `id` — review batch identifier
- `decision_scope` — currently `stepstone_known_candidate_suppression`
- `aggregator_sources` — source names inspected, currently usually `stepstone`
- `company_count`, `suppressed_count`, `kept_for_discovery_review_count`, `recheck_eligible_known_candidate_count` — review counters
- `reviewed_by` — human or agent label that persisted the snapshot
- `evidence` — JSONB boundary and summary evidence

Boundary:

These batches are review state only. They do not activate sources, register
connectors, write Bronze rows, modify schedules or approve destructive operations.

## aggregator_discovery_suppression_items

Per-company suppression decisions belonging to an aggregator-discovery suppression
batch.

Key fields:

- `batch_id` — owning suppression batch
- `aggregator_source_name` — source that produced the company signal, for example `stepstone`
- `company_name` and `normalized_company_key` — company signal used for matching
- `silver_job_count`, `first_seen_at`, `last_seen_at` — current Silver observation evidence
- `decision` — suppression decision such as `keep_for_discovery_review` or `suppress_known_connector_candidate`
- `handoff_action` — review handoff such as `keep_for_new_candidate_discovery`, `suppress_from_aggregator_discovery` or `queue_employer_origin_recheck`
- `known_candidate_id`, `known_candidate_status`, `known_candidate_source_name` — employer-origin lifecycle reference when matched
- `recheck_eligible`, `recheck_reason` — lifecycle recheck indicator and reason
- `evidence` — JSONB decision snapshot

The handoff action is advisory review state. It does not enqueue, approve or execute
connector work by itself.
