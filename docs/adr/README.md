# Architecture Decision Records (ADRs)

This directory contains Architecture Decision Records (ADRs) for the project.

ADRs document important architectural and technical decisions together with their context, consequences, and rationale.

The goal is not only to document the current state of the system, but also to preserve the reasoning behind architectural evolution over time.

---

# ADR Evolution

The project architecture evolved incrementally:

1. Initial Bronze-layer ingestion foundation
2. Database-level duplicate protection
3. Search-profile-based ingestion
4. Connector-based source abstraction
5. Initial Silver-layer normalization
6. Preparation for multi-source canonical modeling

The ADRs intentionally reflect this evolution.

---

# ADR Index

| ADR | Title | Status |
|---|---|---|
| 001 | Use real job market sources | Accepted |
| 002 | Use Bronze-first architecture | Accepted |
| 003 | Use database-level duplicate protection | Accepted |
| 004 | Use search-profile-based ingestion | Accepted |
| 005 | Use PostgreSQL as primary database | Accepted |
| 006 | Use dockerized local development | Accepted |
| 007 | Use SSH for GitHub authentication | Accepted |
| 008 | Use environment-based configuration | Accepted |
| 009 | Use connector-based ingestion | Accepted |
| 010 | Define a canonical job model for the Silver layer | Accepted |
| 011 | separate technical duplicates from cross source deduplication | Accepted |
| 012 | Prepare Bronze layer for historical job observations | Accepted |
| 013 | Evolve toward a personal job market intelligence platform | Accepted |
| 014 | Document database schema and constraints | Accepted |
| 015 | Use canonical search intent and source capabilities | Accepted |
| 016 | Define ingestion scope and relevance boundaries | Accepted |
| 017 | Prepare API-first dashboard architecture | Proposed |
| 018 | Normalize migration prefixes | Accepted |
| 019 | Separate source heartbeat from ingestion runs | Proposed |
| 020 | Introduce role family classification | Proposed |
| 021 | Expand source capability model before complex sources | Accepted |
| 022 | Define shared source and layer terminology | Accepted |
| 023 | Define search result connector contract | Accepted |
| 024 | Define search quality and relevance evaluation boundary | Accepted |
| 025 | Preserve search-term lineage for quality evaluation | Accepted |

---

# Notes

The ADR structure intentionally stays lightweight.

The project is still evolving and the ADR process is meant to support architectural clarity rather than heavyweight governance.
