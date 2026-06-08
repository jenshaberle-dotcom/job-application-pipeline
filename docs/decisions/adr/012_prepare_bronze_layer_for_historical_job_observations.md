# ADR-012: Prepare Bronze layer for historical job observations

## Status

Accepted

## Context

The project is evolving from a simple ingestion pipeline into a job market intelligence platform.

Initial Bronze ingestion stores source-preserving raw job records and prevents technical duplicates per source.

This is sufficient for idempotent ingestion, but not sufficient for historical analysis.

Future analytics require understanding how job postings change over time.

Relevant future questions include:
- When was a job first seen?
- When was it last seen?
- How many days was it online?
- Did the posting change over time?
- Was it reposted?
- Which source published it first?
- Which sources still show it as active?
- How broadly was the same job distributed?
- How did required skills change over time?

The current model must therefore evolve from storing only unique source jobs toward storing repeated observations or snapshots over time.

---

## Decision

The Bronze layer should be prepared for historical job observations.

The project will distinguish between:
- a source-local job identity
- repeated observations of that job over time
- raw source payloads captured at observation time

The current `raw_jobs` table may continue to represent the latest known source-local job record.

A future Bronze observation table may capture repeated source observations.

Possible future structure:

- `raw_jobs`
  - source-local job identity
  - source name
  - external job id
  - source URL
  - first seen timestamp
  - last seen timestamp
  - latest content hash
  - latest raw payload

- `raw_job_observations`
  - raw job reference
  - ingestion run reference
  - observed timestamp
  - raw payload at observation time
  - content hash
  - change indicator

This prepares the platform for historical analytics without prematurely moving to a separate data lake or warehouse.

---

## Architectural Boundary

Bronze remains source-preserving.

Bronze may track observations and payload changes, but it does not interpret business meaning.

Silver later interprets normalized job fields.

Gold later derives metrics and dashboards from historical observations and canonical job identities.

Historical observation tracking is not the same as semantic cross-source deduplication.

Technical duplicate protection, historical observation tracking, and semantic deduplication remain separate concerns.

---

## Consequences

### Positive

- Historical job-market analytics become possible.
- Job lifetime metrics can be calculated.
- Source freshness and source latency can be measured.
- Reposting and update behavior can be analyzed.
- Future dashboards can show market movement over time.
- Raw payloads remain replayable for later Silver transformations.
- PostgreSQL remains sufficient for the current project stage.

### Negative

- Bronze storage volume will increase.
- Observation logic adds ingestion complexity.
- Content hashing will be needed to detect changes.
- Retention policies may become necessary later.
- Data lake or warehouse integration may become useful in a later phase.

---

## Notes

This decision intentionally does not introduce a separate database technology yet.

PostgreSQL remains the primary database because it supports:
- relational modeling
- constraints
- joins
- JSONB raw payloads
- historical observation tables
- analytical SQL

A future data lake or warehouse may be added later when:
- raw data volume grows significantly
- long-term historical storage becomes expensive in PostgreSQL
- dashboard performance requires analytical marts
- batch processing becomes more important
- cloud deployment becomes part of the project scope

The immediate goal is to keep the architecture evolvable without over-engineering too early.
