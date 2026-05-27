# ADR-029: Define Historical Burden Retention Strategy

## Status

Accepted

## Context

The project now persists historical Bronze, Silver, observation, ingestion-run and source-value data.

This enables source-value analysis, lifecycle evaluation and future windowed trends.

However, the current local database also contains historical burden from earlier project phases, including:

- broad Greenhouse board snapshots
- wildcard or exploratory Greenhouse runs
- commercial aggregator history from StepStone
- local test data
- records with missing or weak lineage
- runs created before current search-term, source-target and matching semantics stabilized

Building 24h, 7d or 30d window functions directly on this full historical dataset would produce technically valid but potentially misleading trends.

At the same time, the project intentionally follows a Bronze-first and raw-first strategy.

Historical data should therefore not be deleted only because it is noisy.

The project needs a retention strategy that separates:

- preserving source evidence
- keeping operational analytics clean
- reducing future cloud and storage burden
- avoiding misleading lifecycle scores
- identifying true test or transient data
- preparing archival options

## Decision

The project will treat historical burden management as a classification and retention problem, not as an immediate deletion task.

Before implementing destructive cleanup, the project must classify historical data into retention categories and decide how each category should be treated by operational analytics, trend scoring and future archival workflows.

No manual ad-hoc `DELETE` statements should be used as the default cleanup mechanism.

Future cleanup actions should be implemented as explicit, reviewable and preferably dry-run-capable scripts.

The default retention strategy is:

1. analyze historical burden read-only
2. classify historical subsets by evidence value and operational relevance
3. exclude unsuitable subsets from trend scoring before deleting anything
4. archive or export valuable but operationally noisy history before removing it from the hot database
5. delete only clearly transient, test or invalid data after explicit review

## Retention Categories

Historical data should be classified into categories such as:

| Category | Meaning | Default treatment |
|---|---|---|
| `high_value_historical` | Historical evidence with clear analytical value and sufficient lineage. | Keep in the operational database and allow for trend or lifecycle analysis when appropriate. |
| `ordinary_operational_history` | Normal source history produced by current or mostly stable semantics. | Keep in the operational database. |
| `analysis_only_history` | Useful for source evaluation, debugging or methodology review, but risky for direct trend scoring. | Keep initially, but exclude from lifecycle scoring by default. |
| `aggregator_noise` | Aggregator-derived history with high duplicate pressure or weak origin confidence. | Keep for review and overlap analysis; exclude from canonical source-value trends unless explicitly included. |
| `legacy_broad_match` | Records from old broad-board or wildcard semantics that would be filtered differently today. | Keep as evidence initially; exclude from current source-value trends by default. |
| `missing_lineage` | Records without sufficient profile, run, source-target or search-term lineage. | Review manually; usually exclude from trend scoring. |
| `transient` | Short-lived operational data that has no long-term analytical value. | Candidate for deletion after review. |
| `test_data` | Manual tests, smoke checks or early local experiments. | Candidate for deletion after review. |
| `invalid_or_corrupt` | Records that are technically unusable or misleading. | Candidate for deletion after review and documentation. |

These categories are not meant to replace Bronze evidence preservation.

They define how historical records should be treated by operational analytics and future lifecycle scoring.

## Trend Eligibility

Retention category and trend eligibility are separate concepts.

A record can be worth keeping but still be excluded from current trend scoring.

Examples:

- broad Greenhouse board records may be useful to understand source behavior but should not inflate current 7d or 30d source-value scores
- StepStone aggregator history may be useful for discovery and overlap analysis but should not be treated as employer-origin market evidence
- missing-lineage records may be useful for debugging old pipeline behavior but should not drive lifecycle recommendations
- test records may be useful only until their origin is understood, then become deletion candidates

Future Gold and source-value views should therefore be able to distinguish at least:

- retained evidence
- trend-eligible evidence
- excluded historical evidence
- archive candidates
- deletion candidates

## Cleanup Safety Rules

Cleanup must remain defensive and reviewable.

The following safety rules apply:

- cleanup scripts must support dry-run mode first
- destructive actions must be explicit, not default behavior
- selection criteria must be visible in SQL or script output
- expected affected row counts must be shown before deletion
- important source evidence should be exportable before removal
- test-data deletion must not accidentally match real source records
- Bronze should not be aggressively filtered to make the database look clean
- lifecycle or trend exclusions should be preferred over deletion when historical value is uncertain

## Archive Direction

If historical burden grows materially, the preferred future direction is not immediate deletion.

Possible archival options include:

- exporting old Bronze records to JSONL or Parquet
- moving old records to archive tables
- keeping aggregate source-value snapshots in the hot database while moving raw payloads to cold storage
- retaining only canonical identifiers, run metadata and source evidence references in operational tables

This is especially relevant before any cloud deployment, where storage, indexing and backup costs become real operational concerns.

## Consequences

### Positive

- prevents misleading trend metrics before window functions are implemented
- keeps Bronze compatible with a raw-first evidence model
- makes cleanup decisions auditable
- reduces the risk of deleting useful historical evidence too early
- prepares future cloud cost and storage optimization
- separates source-value scoring from raw data preservation

### Negative

- requires an additional classification step before cleanup
- delays visible database size reduction
- adds more conceptual categories to maintain
- future scripts must distinguish retention, trend eligibility and deletion eligibility

## Implementation Notes

The current read-only script remains the baseline diagnostic tool:

```bash
python -m scripts.analyze_historical_burden --limit 30
```

Future implementation should add a dry-run cleanup or review script before any destructive action.

A likely next script could produce a candidate table or export with fields such as:

- `burden_category`
- `source_name`
- `profile_name`
- `search_term_snapshot`
- `raw_job_count`
- `observation_count`
- `silver_job_count`
- `first_seen_at`
- `latest_seen_at`
- `trend_eligible`
- `recommended_retention_action`
- `review_reason`

This should remain separate from the ingestion runner.

Cleanup and retention are platform lifecycle concerns, not connector behavior.

## Related ADRs

- ADR-002: Use Bronze-first architecture
- ADR-011: Separate technical duplicates from cross-source deduplication
- ADR-012: Prepare Bronze layer for historical job observations
- ADR-024: Define search quality and relevance evaluation boundary
- ADR-025: Preserve search-term lineage for quality evaluation
- ADR-026: Define source acquisition scope, canonical source strategy and source value evaluation
- ADR-028: Separate source family, source target and source type
