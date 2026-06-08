# ADR-005 — Use PostgreSQL as Primary Database

## Status

Accepted

---

## Context

The project requires:
- structured relational storage
- transactional consistency
- indexing support
- JSON storage capabilities
- realistic enterprise relevance

The system must support:
- ingestion metadata
- relational references
- raw JSON payloads
- future normalization layers

SQLite was considered but rejected due to limited scalability and lower production relevance.

---

## Decision

Use PostgreSQL 17 as the primary persistence layer.

The database runs locally inside Docker during development.

---

## Consequences

### Positive

- strong relational capabilities
- mature indexing support
- JSONB support
- enterprise relevance
- scalable architecture
- realistic production similarity

### Negative

- slightly higher setup complexity
- more operational overhead than SQLite
