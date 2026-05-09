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
