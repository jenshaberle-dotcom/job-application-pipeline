# Historical Burden Review

## Status

Current H2 review artifact.

This document captures the project interpretation of historical burden after introducing the dry-run retention review workflow. It is not a deletion log and does not authorize destructive cleanup by itself.

## Purpose

The project intentionally started with tolerant Bronze ingestion. That was useful because it surfaced real source behavior and avoided premature filtering.

However, the local database now contains historical records from earlier, broader semantics. Some of these records are useful to explain project evolution, but they are not automatically useful as long-term operational data.

The review therefore separates:

- evidence worth keeping in the hot operational database
- ordinary operational history
- historical burden that should be exported before hot-store removal
- true delete candidates

## Current Review Result

The current dry-run export produced the following totals:

| Review track | Rows | Interpretation |
|---|---:|---|
| `archive_before_hot_store_removal_candidate` | 752 | Historical burden with explanatory or archival value, but weak long-term hot-store value. |
| `retain_as_silver_evidence` | 82 | Raw rows backed by Silver evidence; keep operationally. |
| `retain_operational_history` | 21 | Ordinary operational history; keep for now. |
| `delete_candidate_after_review` | 2 | Clear test/transient candidates; delete only after explicit review. |
| **Total** | **857** | Full raw-job review coverage. |

The detail export and the summary export intentionally cover the same total row count.

## Archive Export Result

The local archive export workflow preserves rows classified as:

```text
archive_before_hot_store_removal_candidate
```

The current archive manifest produced these totals:

| Metric | Value |
|---|---:|
| Archive record count | 752 |
| Silver-backed rows in archive | 0 |
| Raw-data payload size | 674.8 kB |
| `greenhouse:stripe` rows | 589 |
| `stepstone` rows | 163 |

Burden category split:

| Burden category | Rows |
|---|---:|
| `greenhouse_without_current_matching_metadata` | 482 |
| `greenhouse_legacy_wildcard` | 107 |
| `commercial_aggregator_history` | 163 |

The archive workflow writes JSONL records, a summary CSV and a manifest with checksums. It does not delete or update database rows. The archive proves that explanatory evidence exists before any later hot-store removal step is considered.

## Hot-Store Removal Dry-Run Result

After creating the local archive artifact, the hot-store removal dry-run validates the archive manifest and checksum, compares archived `raw_job_id` values against the current database state and exports a review list.

The current dry-run produced:

| Metric | Value |
|---|---:|
| Candidate rows | 752 |
| Eligible for future removal after archive review | 752 |
| Blocked or non-actionable rows | 0 |
| Silver-backed rows now | 0 |

Source split:

| Source | Rows |
|---|---:|
| `greenhouse:stripe` | 589 |
| `stepstone` | 163 |

This is still not a cleanup action. It is a review artifact that answers: "which archived rows would be eligible if the project later introduces an explicit removal command?"

## Guarded Hot-Store Removal Command

After archive export and dry-run review, the project now has a guarded command that can prepare a hot-store removal execution plan:

```bash
python -m scripts.remove_historical_burden_from_hot_store \
  --review-dir exports/historical_burden_hot_store_removal_review \
  --output-dir exports/historical_burden_hot_store_removal_execution
```

The command defaults to dry-run mode. The current dry-run result was:

| Metric | Value |
|---|---:|
| Planned candidates | 752 |
| Eligible now | 752 |
| Blocked now | 0 |
| Executed removal | false |

The command validates the prior review manifest and candidates CSV checksum, re-checks current database state and blocks rows whose source, classification or Silver-evidence status changed.

Execute mode is intentionally noisy. It requires all of the following confirmations before it can mutate the hot store:

```bash
--execute
--confirm-retention-track archive_before_hot_store_removal_candidate
--confirm-candidate-count 752
--confirm-candidates-sha256 <validated-removal-candidates-csv-sha256>
--confirm-cleanup-action remove_archived_historical_burden_from_hot_store
--allow-source greenhouse:stripe
--allow-source stepstone
```

This document does not claim that execute mode has been run. It documents that the project now has a guarded path from historical-burden classification to archive evidence, dry-run review and optional future hot-store removal.

This workflow is separate from test-data cleanup. The two `delete_candidate_after_review` rows are better handled by a dedicated test/transient cleanup workflow, not by the archive-before-hot-store-removal path.

## Greenhouse Stripe Interpretation

Legacy `greenhouse:stripe` history is the main example of differentiated historical burden.

The project does not treat all Greenhouse data as low value. Rows with Silver evidence remain retained evidence.

The burden concern is specifically about older full-fetch or wildcard rows without Silver evidence. These records document an important learning step: broad, undifferentiated ingestion can create significant volume without equivalent project value.

For local H2 review this history is useful. It shows how the pipeline evolved and why source-value evaluation must consider evidence quality, not only row counts.

For a future cloud hot store, the balance changes. Once the review export and documentation exist, keeping all legacy noisy rows operationally has limited value and increases cost, backup size, index burden, query complexity and the risk of accidentally including them in Trend or Gold views.

The intended lifecycle is therefore:

```text
short term:
  keep locally until H2 review, export and documentation are complete

medium term:
  export, document and exclude from Trend/Gold calculations

long term:
  remove from the operational hot database or move to cold storage/archive before cloud migration
```

## What This Means for the Project Story

The project can explain the evolution honestly:

- early ingestion was intentionally broad and raw-first
- broad Greenhouse ingestion created volume
- the project identified that the volume did not provide proportional value
- this led to source-value evaluation, historical burden analysis and retention thinking
- the final product becomes cleaner because historical burden is classified before Gold trends and cloud migration

This is a deliberate data-engineering maturity step, not a failed experiment.

## Boundaries

This review does not change Bronze ingestion behavior. Bronze remains tolerant and raw-first.

This review does not delete rows. It prepares review tracks, export evidence and guarded execution plans.

This review does not make all historical data ineligible for trends. Trend eligibility depends on lineage, evidence quality and retention track.

This review does not treat Greenhouse as globally low value. It distinguishes Silver-backed evidence from old broad-match or wildcard history without current evidence.

The guarded removal command exists, but execute mode is a separate operational decision. Until execute mode is run deliberately, the affected rows remain in the local hot-store database.

## Related Artifacts

- `scripts.analyze_historical_burden`
- `scripts.review_historical_burden_candidates`
- `scripts.export_historical_burden_archive`
- `scripts.prepare_historical_burden_hot_store_removal`
- `scripts.remove_historical_burden_from_hot_store`
- ADR-029: Define Historical Burden Retention Strategy
- `docs/source_evaluation.md`
