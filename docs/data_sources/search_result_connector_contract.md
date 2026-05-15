# Search Result Connector Contract

## Purpose

This document defines the expected shape and semantics of search-result-oriented connectors.

It supports the connector architecture before adding more complex sources such as StepStone, Workday-like sources or direct employer career pages.

The goal is not to normalize all sources immediately.

The goal is to make connector output comparable while still preserving source-specific evidence in the Bronze layer.

See also:

- `docs/adr/009_use_connector_based_ingestion.md`
- `docs/adr/010_define_canonical_job_model_for_silver_layer.md`
- `docs/adr/022_define_shared_source_and_layer_terminology.md`
- `docs/adr/023_define_search_result_connector_contract.md`

---

## Current Code-Level Structure

The current connector output structure is `RawJobRecord`.

```python
@dataclass(frozen=True)
class RawJobRecord:
    source_name: str
    source_url: str
    external_job_id: str | None
    raw_data: dict[str, Any]
```

This structure remains intentionally small.

The connector contract should be documented before introducing more fields into the code or database schema.

---

## Required Project-Level Fields

| Field | Required | Meaning |
|---|---:|---|
| `source_name` | yes | Stable project-level source name. |
| `source_url` | yes | Best available source URL for the job record. |
| `external_job_id` | no | Stable or likely stable source-side job identifier. |
| `raw_data` | yes | Source-preserving payload and extraction evidence. |

---

## Recommended Raw Data Shape

For search-result-based sources, `raw_data` should preserve extracted result-card fields and source-specific evidence.

Recommended shape:

```json
{
  "result_card": {
    "title": "...",
    "company_name": "...",
    "location": "...",
    "detail_url": "...",
    "external_job_id_candidate": "..."
  },
  "source_specific": {
    "article_id": "...",
    "data_testid": "job-item",
    "title_link_id": "...",
    "selector_version": "..."
  },
  "extraction": {
    "extracted_from": "search_result_page",
    "detail_page_fetched": false,
    "pagination_used": false
  }
}
```

This is a documentation target, not yet a mandatory schema.

---

## Field Semantics

### `source_name`

Stable name used by the project to identify the source.

Examples:

- `bundesagentur`
- `greenhouse`
- `stepstone`

The value should be stable enough for database constraints, dashboards and source-level metrics.

### `source_url`

Best available URL for the record.

For API sources, this may be a source-provided job URL.

For result-card sources, this is usually the detail URL extracted from the result card.

If only a search-result URL is available, the connector should preserve additional context in `raw_data`.

### `external_job_id`

Identifier assigned by the source or derived from source markup or URLs.

Quality levels should be documented in source capabilities:

| Quality | Meaning |
|---|---|
| `stable` | Source clearly provides a stable job ID. |
| `derived` | ID can be derived from URL or markup and appears stable. |
| `unstable` | ID may change between requests or views. |
| `missing` | No usable ID is available. |
| `unknown` | Not evaluated yet. |

### `source_result_id`

A `source_result_id` is a source-specific result-card identifier.

It should be used in documentation or raw metadata when an ID has been observed but not yet proven to be a stable job identifier.

A `source_result_id` should not automatically become `external_job_id`.

### `detail_url`

A `detail_url` points to a fuller job detail page.

A connector may expose it as `source_url` if it is the best available source URL.

It should also be preserved in `raw_data` for traceability.

### `raw_data`

`raw_data` is the current code-level field for source-preserving payload.

Documentation may also use the term `raw_payload` when describing architecture, but the current Python field remains `raw_data`.

---

## Bronze, Silver and Canonical Boundaries

Bronze:

- stores source provenance
- keeps source-specific raw fields
- preserves extraction evidence
- avoids premature normalization

Silver:

- maps source-specific fields into canonical fields
- applies normalization rules
- handles source-specific gaps and inconsistencies
- prepares cross-source comparison

Gold:

- serves dashboards, metrics and business-facing views
- must not depend on HTML selectors or source-specific result-card structures

---

## StepStone Example

Observed StepStone signal:

```text
article[data-testid="job-item"]
```

Project interpretation:

```text
result card
```

Observed candidate fields:

| Observed Field | Project Interpretation |
|---|---|
| article ID | source-specific result-card evidence |
| title text | result card title |
| company text | result card company |
| location text | result card location |
| href | detail URL |
| numeric ID in URL | external job ID candidate |

Important rule:

The numeric ID should only be promoted from candidate to `external_job_id` after stability has been validated.

Current StepStone status:

```text
experimental spike only
```

---

## Out of Scope

This contract does not yet define:

- production StepStone ingestion
- detail-page scraping
- browser automation
- pagination traversal
- cross-source deduplication
- Silver-layer canonical transformation rules
- database migration changes

These topics should be handled in later, smaller decisions.
