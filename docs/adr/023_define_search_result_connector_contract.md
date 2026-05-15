# ADR-023: Define search result connector contract

## Status

Accepted

## Context

The project ingests job data from different source types, including public APIs, ATS job boards, commercial job portals and potentially direct employer career pages.

These sources differ strongly in access patterns, available fields, identifiers, filtering capabilities, pagination behavior and operational risk.

The project already uses a connector-based ingestion architecture and a shared source and layer terminology. However, before implementing more complex sources such as StepStone, the project needs a small common contract for search-result-oriented connectors.

Without such a contract, each connector could accidentally define its own field semantics. This would make Bronze records harder to compare and would weaken later Silver-layer normalization.

StepStone is the main current driver for this decision, but the contract is intentionally source-independent.

## Decision

The project defines a search result connector contract.

A search result connector is expected to produce source-preserving Bronze records while exposing a small set of comparable project-level fields.

The minimum project-level fields are:

| Field | Meaning |
|---|---|
| `source_name` | Stable project name of the source, for example `bundesagentur`, `greenhouse` or `stepstone`. |
| `source_url` | Best available source URL for the record. For search-result sources, this is usually the detail URL if available. |
| `external_job_id` | Identifier assigned by the source or derived from stable source markup or URLs. May be `None` if not available. |
| `raw_data` | Source-preserving payload containing raw/source-specific fields and extraction evidence. |

The following terms are used in documentation and source analysis:

| Term | Meaning |
|---|---|
| `result card` | One search-result item before opening a detail page. |
| `result card fields` | Fields extracted from a result card, for example title, company, location and detail URL. |
| `detail_url` | Source-specific URL pointing to a fuller job detail page. |
| `source_result_id` | Source-specific result-card identifier if it is not yet proven to be a stable external job ID. |
| `external_job_id` | Stable or likely stable source job identifier used for deduplication within a source. |
| `raw_payload` | Documentation term for source-preserving data. The current Python structure stores this as `raw_data`. |

The current code-level transport structure remains `RawJobRecord`.

No immediate database migration is introduced by this ADR.

The contract is documented first. Code and database changes should only follow when a concrete implementation need is proven.

## Layer Rules

Bronze records preserve source evidence.

The Bronze layer may contain source-specific fields inside `raw_data`.

The Silver layer maps source-specific values into canonical project fields.

The Gold layer must not depend on source-specific result-card structures, HTML selectors or provider-specific vocabulary.

## StepStone Application

StepStone remains under evaluation and is not promoted to a production connector by this ADR.

For StepStone, the observed `article[data-testid="job-item"]` structure is treated as a source-specific signal for a project-level result card.

The numeric ID observed in both the article ID and the detail URL may be treated as an `external_job_id` candidate only when both values match.

Until stability has been validated across multiple searches and over time, this ID should still be documented as a candidate rather than an accepted production identifier.

The first StepStone spike should:

- extract result cards only
- avoid detail-page fetching
- avoid pagination
- avoid aggressive crawling
- preserve extraction evidence in raw/source-specific metadata
- avoid writing production ingestion records until the source decision is clearer

## Consequences

This keeps the connector architecture source-independent.

It allows StepStone to be evaluated without forcing premature production design decisions.

It makes future source comparisons easier because all sources can be discussed using the same contract language.

It also avoids unnecessary database churn while the project is still learning from complex sources.

## Alternatives Considered

### Build the StepStone connector directly

Rejected for now.

StepStone is a commercially operated job portal with higher technical, operational and legal risk than the currently implemented API/ATS sources.

Building the connector before defining the contract would allow StepStone-specific assumptions to leak into the general architecture.

### Add new database columns immediately

Rejected for now.

The current `RawJobRecord` structure is sufficient for the next evaluation step.

Additional columns such as `detail_url`, `source_result_id` or `ingested_at` may become useful later, but should be introduced only when the model pressure is clear.

### Keep each connector fully source-specific

Rejected.

Source-specific raw evidence belongs in Bronze, but the connector boundary should still expose a small comparable project-level contract.
