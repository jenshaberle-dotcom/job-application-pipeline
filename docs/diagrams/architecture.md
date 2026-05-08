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

    class FutureConnector {
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
    }

    class silver_jobs {
        <<Future Silver Layer>>
    }

    class skills {
        <<Future Silver Layer>>
    }

    class job_skills {
        <<Future Silver Layer>>
    }

    JobSourceConnector <|.. BundesagenturConnector
    JobSourceConnector <|.. FutureConnector

    JobIngestionRunner --> JobSourceConnector
    JobIngestionRunner --> JobIngestionRepository

    BundesagenturConnector --> RawJobRecord
    FutureConnector --> RawJobRecord

    JobIngestionRepository --> SearchProfile
    JobIngestionRepository --> SearchTerm
    JobIngestionRepository --> raw_jobs

    raw_jobs ..> silver_jobs : later normalization
    raw_jobs ..> skills : later extraction
    raw_jobs ..> job_skills : later extraction
