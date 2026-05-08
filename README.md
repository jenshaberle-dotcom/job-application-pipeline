# Job Application Pipeline

## Vision

This project aims to build an automated end-to-end job ingestion and analysis pipeline.

The goal is to collect job postings from multiple sources, store them in a structured data platform, remove duplicates, normalize content and evaluate job postings based on custom matching criteria.

The project is designed as both:
- a personal learning journey towards Data Engineering
- and a production-oriented showcase project

The focus is intentionally placed on:
- realistic data sources
- maintainable architecture
- reproducible environments
- pragmatic security concepts
- explainable engineering decisions

---

## Architecture

The pipeline follows a layered data architecture inspired by modern data platforms and Microsoft Fabric concepts.

The ingestion layer follows a **connector-based architecture**.

Source-specific access logic is implemented in connectors, while the ingestion runner handles orchestration and the repository handles database persistence.

This keeps the Bronze layer source-preserving and prepares the project for adding further sources and later Silver-layer normalization.

### Connector Architecture

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
