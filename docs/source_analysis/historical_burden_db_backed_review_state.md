# Historical Burden DB-Backed Review State — S2O-B

## Status

Implemented as Stage 1 and Stage 2.

S2O-B replaces the historical-burden hot-store removal review handoff with database-backed proposed review state.

## Purpose

Historical-burden rows may eventually be removed from the hot Bronze store after careful review. That workflow is retention-changing and potentially destructive, so it must not depend on a generated local CSV/manifest handoff.

The review state now belongs in the database.

Generated Markdown/JSON files may still be useful for human inspection, but they are review artifacts only. They must not be used as pipeline inputs, activation gates, execution inputs, migration inputs or cloud dependencies.

## Database Model

S2O-B adds:

- `historical_burden_review_batches`
- `historical_burden_review_items`

A batch represents one proposed review set. Items snapshot the raw job identifiers and review-relevant evidence at the time the batch was created.

`historical_burden_review_items.raw_job_id` is intentionally not a foreign key to `raw_jobs`. The review item must remain auditable even after a later approved hot-store removal deletes the raw row.

## Current Stage

Stage 1 creates proposed DB-backed review batches.

The prepare script:

```bash
python -m scripts.prepare_historical_burden_hot_store_removal
```

does this:

1. reads current database evidence
2. classifies historical-burden candidates
3. stores a proposed review batch in the database
4. writes Markdown/JSON review artifacts for humans

It does not delete, update or archive database rows.

## Stage 2 Execution Path

Stage 2 refactors the guarded hot-store removal command to use DB-backed review state.

The command now requires `--batch-id` and reads `historical_burden_review_batches` plus `historical_burden_review_items`.

Default behavior is dry-run:

```bash
python -m scripts.remove_historical_burden_from_hot_store --batch-id <batch_id>
```

Approval is explicit and updates only database review state:

```bash
python -m scripts.remove_historical_burden_from_hot_store   --batch-id <batch_id>   --approve   --confirm approve_historical_burden_hot_store_removal_batch
```

Execution is destructive and requires an approved DB batch plus exact confirmation:

```bash
python -m scripts.remove_historical_burden_from_hot_store   --batch-id <batch_id>   --execute   --confirm remove_approved_historical_burden_from_hot_store
```

The command revalidates current hot-store state before approval and execution. It blocks rows that are missing, already processed, no longer match the stored source name, have Silver evidence, or are no longer eligible.

Markdown/JSON outputs remain reports only.

## Cloud Boundary

This design avoids local file handoffs as operational dependencies.

It prepares the removal workflow for cloud/CI operation by making review state durable, queryable and auditable in the project database.
