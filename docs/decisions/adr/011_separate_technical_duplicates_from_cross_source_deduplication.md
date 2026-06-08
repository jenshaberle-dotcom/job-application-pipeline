# ADR-011: Separate technical duplicate protection from cross-source deduplication

## Status

Accepted

## Context

The current Bronze-layer ingestion pipeline already prevents exact technical duplicates using database-level constraints.

This currently works well for:
- repeated ingestion runs
- source retries
- idempotent ingestion behavior
- duplicate records originating from the same source

However, this strategy is intentionally limited to source-local technical duplicates.

As the platform evolves toward multi-source ingestion, the same real-world job posting may appear across multiple systems such as:
- Greenhouse
- StepStone
- company career pages
- ATS platforms
- aggregators

These records may:
- have different identifiers
- contain different metadata
- contain different formatting
- contain incomplete fields
- differ slightly semantically

Despite this, they may still represent the same real-world job posting.

The existing Bronze duplicate protection is not sufficient for this problem.

---

## Decision

The project separates:
- technical duplicate protection
- cross-source semantic deduplication

Technical duplicate protection remains a Bronze-layer responsibility.

Cross-source deduplication becomes a later Silver-layer responsibility.

Bronze continues to:
- preserve raw source records
- preserve source-specific identifiers
- remain source-preserving
- avoid semantic interpretation

Silver later becomes responsible for:
- canonical comparison
- normalization
- semantic comparison
- duplicate candidate identification
- canonical job grouping

The architecture intentionally avoids prematurely merging records during ingestion.

---

## Architectural Direction

The project may later introduce structures such as:
- `canonical_jobs`
- `canonical_job_sources`
- `job_identity_candidates`

This would allow:
- multiple source records
- to reference a shared canonical job identity
- while preserving full source traceability

Example structure:

- canonical_job
  - greenhouse:stripe
  - stepstone
  - company_career_page

The project intentionally prefers traceable grouping over destructive merging.

---

## Consequences

### Positive

- Bronze remains simple and source-preserving.
- Multi-source ingestion remains flexible.
- Original source payloads remain accessible.
- Cross-source logic can evolve independently.
- Future semantic matching becomes easier.
- Analytics can later operate on canonical identities instead of raw postings.

### Negative

- Duplicate handling becomes a multi-stage process.
- Canonical identity modeling adds complexity.
- Similarity logic may become computationally expensive.
- Ambiguous cases may require probabilistic matching.
- Canonical grouping logic may evolve significantly over time.

---

## Notes

The project intentionally treats:
- ingestion
- normalization
- semantic identity
- analytics

as separate architectural concerns.

This avoids tightly coupling the platform to:
- source-specific identifiers
- source-specific semantics
- source-specific formatting assumptions

The project also intentionally avoids premature analytical modeling such as Star or Snowflake schemas in the Silver layer.

The Silver layer is currently treated as:
- a canonical operational model
- not an analytical warehouse model

Future Gold-layer analytics may later introduce:
- Star schemas
- dimensions
- facts
- KPI-oriented analytical models
