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
        +source_name
        +external_job_id
        +raw_data
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

    class matching_scores {
        <<Future Gold Layer>>
    }

    JobSourceConnector <|.. BundesagenturConnector
    JobSourceConnector <|.. FutureConnector

    JobIngestionRunner --> JobSourceConnector : executes
    JobIngestionRunner --> JobIngestionRepository : persists via

    JobIngestionRepository --> SearchProfile
    JobInestionRepository --> SearchTerm
    JobIngestionRepository --> raw_jobs

    BundesagenturConnector --> RawJobRecord : returns
    FutureConnector --> RawJobRecord : returns

    RawJobRecord --> raw_jobs : source-preserving storage

    raw_jobs ..> silver_jobs : later normalization
    raw_jobs ..> skills : later extraction
    raw_jobs ..> job_skills : later extraction

    silver_jobs ..> matching_scores : later scoring
