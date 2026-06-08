# ADR-006 — Use Dockerized Local Development

## Status

Accepted

---

## Context

The project requires:
- reproducible local environments
- isolated infrastructure
- simplified onboarding
- realistic deployment behavior

Installing PostgreSQL directly on the host system would increase:
- environment drift
- configuration inconsistency
- local setup complexity

---

## Decision

Run PostgreSQL inside Docker containers during local development.

Docker Desktop with WSL2 integration is used as the local container runtime.

---

## Consequences

### Positive

- reproducible environments
- simplified local setup
- easier environment reset
- infrastructure isolation
- closer production similarity

### Negative

- additional tooling complexity
- dependency on Docker Desktop
- increased resource usage
