# Connector Architecture

```mermaid
classDiagram
    class JobSourceConnector {
        <<interface>>
        +source_name
        +fetch_jobs(profile, search_term)
    }

    class BundesagenturConnector {
        +source_name
        +fetch_jobs(profile, search_term)
    }

    class GreenhouseConnector {
        +source_name
        +fetch_jobs(profile, search_term)
    }

    class StepStoneConnector {
        +source_name
        +fetch_jobs(profile, search_term)
    }

    class JobIngestionRunner {
        +run(profile_name)
    }

    class JobIngestionRepository {
        +load_active_search_terms(profile_name)
        +create_ingestion_run(...)
        +save_raw_job(...)
        +finish_ingestion_run(...)
    }

    class SilverJobRepository {
        +load_unprocessed_raw_jobs(limit)
        +upsert_silver_job(job)
    }

    class SearchProfile {
        +id
        +profile_name
        +source_name
        +search_location
        +search_radius_km
        +offer_type
        +page_size
    }

    class SearchTerm {
        +search_term
    }

    class RawJobRecord {
        +source_name
        +source_url
        +external_job_id
        +raw_data
    }

    class raw_jobs {
        <<Bronze Layer>>
        +source_name
        +external_job_id
        +raw_data
    }

    class silver_jobs {
        <<Silver Layer>>
        +raw_job_id
        +title
        +company_name
        +city
        +publication_date
        +normalized_title
        +normalized_company_name
        +canonical_key_candidate
    }

    class matching_scores {
        <<Future Gold Layer>>
    }

    JobSourceConnector <|.. BundesagenturConnector
    JobSourceConnector <|.. GreenhouseConnector
    JobSourceConnector <|.. StepStoneConnector

    JobIngestionRunner --> JobSourceConnector : executes
    JobIngestionRunner --> JobIngestionRepository : persists via

    JobIngestionRepository --> SearchProfile
    JobIngestionRepository --> SearchTerm
    JobIngestionRepository --> raw_jobs

    BundesagenturConnector --> RawJobRecord : returns
    GreenhouseConnector --> RawJobRecord : returns
    StepStoneConnector --> RawJobRecord : returns

    RawJobRecord --> raw_jobs : source-preserving storage

    SilverJobRepository --> raw_jobs : reads unprocessed records
    SilverJobRepository --> silver_jobs : writes normalized records

    raw_jobs ..> silver_jobs : source-aware normalization
    silver_jobs ..> matching_scores : later scoring
```

## Boundary Notes

Connectors fetch and transport source-specific job data.

They do not perform business-level interpretation such as:
- skill extraction
- company normalization
- location normalization
- deduplication across sources
- CV-to-job matching

The Bronze layer stores source-preserving raw records.

The Silver layer provides a pragmatic canonical representation and now includes first-stage canonicalization fields for duplicate-candidate and source-value analysis.
