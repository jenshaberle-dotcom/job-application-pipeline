# System Architecture

```mermaid
flowchart LR

    Sources[Job Sources]

    Sources --> BA[Bundesagentur für Arbeit]
    Sources --> StepStone[StepStone]
    Sources --> LinkedIn[LinkedIn Jobs]
    Sources --> Greenhouse[Greenhouse ATS]
    Sources --> Workday[Workday]

    BA --> Ingestion
    StepStone --> Ingestion
    LinkedIn --> Ingestion
    Greenhouse --> Ingestion
    Workday --> Ingestion

    Ingestion[Ingestion Layer]

    Ingestion --> SearchProfiles[search_profiles]
    Ingestion --> IngestionRuns[ingestion_runs]
    Ingestion --> RawJobs[raw_jobs]

    RawJobs --> Silver[Silver Layer]
    Silver --> Gold[Gold Layer]

    Gold --> Matching[Matching Engine]
    Gold --> Dashboard[Dashboards & Analytics]
```
