# ADR-003 — Use Database-Level Duplicate Protection

## Status

Accepted

---

## Context

The ingestion pipeline repeatedly loads job postings from external sources.

The system must prevent:
- duplicate inserts
- inconsistent ingestion behavior
- race conditions during parallel ingestion
- uncontrolled database growth

Application-level duplicate checks alone are insufficient because:
- multiple ingestion processes may run simultaneously
- source data may overlap across search terms
- future schedulers may trigger concurrent executions

---

## Decision

Duplicate protection is enforced at the database level.

The current strategy uses:
- unique index on `(source_name, external_job_id)`
- PostgreSQL `ON CONFLICT DO NOTHING`

The ingestion pipeline therefore becomes idempotent.

---

## Consequences

### Positive

- strong data integrity guarantees
- idempotent ingestion behavior
- simplified application logic
- protection against concurrent inserts
- scalable ingestion architecture

### Negative

- database constraints become part of ingestion logic
- duplicate handling requires stable source identifiers
- future fuzzy matching still requires additional logic
