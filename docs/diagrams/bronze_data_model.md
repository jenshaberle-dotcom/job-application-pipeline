# Bronze and Silver Data Model

```mermaid
erDiagram

    search_profiles {
        BIGINT id PK
        TEXT profile_name UK
        TEXT source_name
        TEXT search_term
        TEXT search_location
        INTEGER search_radius_km
        INTEGER offer_type
        INTEGER page_size
        BOOLEAN is_active
        TIMESTAMPTZ created_at
    }

    search_terms {
        BIGINT id PK
        BIGINT search_profile_id FK
        TEXT search_term
        BOOLEAN is_active
        TIMESTAMPTZ created_at
    }

    ingestion_runs {
        BIGINT id PK
        TEXT source_name
        BIGINT search_profile_id FK
        TIMESTAMPTZ started_at
        TIMESTAMPTZ finished_at
        TEXT status
        TEXT requested_url
        INTEGER total_loaded
        INTEGER inserted_count
        INTEGER duplicate_count
        TEXT error_message
    }

    raw_jobs {
        BIGINT id PK
        TEXT source_name
        TEXT source_url
        TEXT external_job_id
        TIMESTAMPTZ fetched_at
        JSONB raw_data
        TEXT content_hash
        TIMESTAMPTZ created_at
        BIGINT ingestion_run_id FK
        BIGINT search_profile_id FK
    }

    silver_jobs {
        BIGINT id PK
        BIGINT raw_job_id FK_UK
        TEXT source_name
        TEXT external_job_id
        TEXT source_url
        TEXT title
        TEXT company_name
        TEXT city
        TEXT postal_code
        TEXT country
        DATE publication_date
        TIMESTAMPTZ normalized_at
        TIMESTAMPTZ created_at
        TIMESTAMPTZ updated_at
    }

    search_profiles ||--o{ search_terms : defines
    search_profiles ||--o{ ingestion_runs : executes
    search_profiles ||--o{ raw_jobs : categorizes
    ingestion_runs ||--o{ raw_jobs : produces
    raw_jobs ||--o| silver_jobs : normalizes_to
```

## Relationship Rationale

| Relationship | Cardinality | Meaning |
|---|---:|---|
| `search_profiles` → `search_terms` | 1:n | One profile can contain multiple active search terms. |
| `search_profiles` → `ingestion_runs` | 1:n | One profile can be executed repeatedly. |
| `search_profiles` → `raw_jobs` | 1:n | Raw jobs keep the profile context that produced them. |
| `ingestion_runs` → `raw_jobs` | 1:n | One ingestion run can produce many raw records. |
| `raw_jobs` → `silver_jobs` | 1:0..1 | A raw job can have at most one normalized Silver representation. |

## Key Constraints

| Table | Constraint | Meaning |
|---|---|---|
| `search_profiles` | `profile_name` unique | Profile names can be used as stable execution identifiers. |
| `search_terms` | `search_profile_id, search_term` unique | Prevents duplicate search terms within the same profile. |
| `raw_jobs` | partial unique index on `source_name, external_job_id` where `external_job_id IS NOT NULL` | Prevents technical duplicates from the same source. |
| `silver_jobs` | `raw_job_id` unique | Ensures one Silver row per Bronze row. |

## Design Notes

`raw_jobs` is the source-preserving Bronze table.

`silver_jobs` is the first canonical Silver representation.

`search_profiles` define reusable ingestion configuration.

`search_terms` define the active keyword intent per profile.

`ingestion_runs` provide operational lineage and ingestion statistics.

## Known Limitation

The database currently tracks profile and ingestion lineage.

It does not yet persist whether a filter was applied server-side by the source or locally after fetching. This is introduced first as connector capability metadata in code.
