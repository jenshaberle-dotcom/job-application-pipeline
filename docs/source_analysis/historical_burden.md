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

This review does not delete rows. It prepares review tracks and export evidence.

This review does not make all historical data ineligible for trends. Trend eligibility depends on lineage, evidence quality and retention track.

This review does not treat Greenhouse as globally low value. It distinguishes Silver-backed evidence from old broad-match or wildcard history without current evidence.

## Related Artifacts

- `scripts.analyze_historical_burden`
- `scripts.review_historical_burden_candidates`
- ADR-029: Define Historical Burden Retention Strategy
- `docs/source_evaluation.md`
