# Finanz Informatik Activation Gate Review — S2N

## Purpose

S2N evaluates whether Finanz Informatik may move from connector candidate to a controlled inactive source-target preview.

This review is intentionally DB-backed and connector-preview-backed.

## Architectural Rule

Generated review artifacts are outputs, not durable pipeline inputs.

The S2N decision must be generated from:

- a live bounded Finanz Informatik connector-candidate preview
- current database evidence
- reused S2L incremental-uniqueness comparison logic

If the database is unavailable, S2N must fail instead of producing an activation decision.

## Why This Matters

Activation gates must be reproducible in local development, CI and later cloud environments. A local artifact from an earlier manual step can be useful for review, but it must not become the hidden input for a decision gate.

S2N therefore generates the current evidence during the run and writes review artifacts only after the decision has been built from live connector and database evidence.

## Workflow

Set DB environment variables first, for example by loading `.env` and mapping `POSTGRES_*` to `PG*` variables:

    set -a
    source .env
    set +a

    export PGHOST="${POSTGRES_HOST:-localhost}"
    export PGPORT="${POSTGRES_PORT:-5432}"
    export PGDATABASE="$POSTGRES_DB"
    export PGUSER="$POSTGRES_USER"
    export PGPASSWORD="$POSTGRES_PASSWORD"

Then run:

    python -m scripts.review_finanz_informatik_activation_gate

Finally clear the password from the shell:

    unset PGPASSWORD

## Outputs

S2N writes review artifacts to:

    exports/s2n_finanz_informatik_activation_gate/

Expected files:

- `finanz_informatik_activation_gate_review.md`
- `finanz_informatik_activation_gate_manifest.json`

These files are outputs only and should not be committed.

## Decision Semantics

Possible per-candidate decisions:

- `activation_gate_incremental_value_candidate`
- `activation_gate_needs_manual_overlap_review`
- `activation_gate_defer_known_elsewhere`
- `activation_gate_blocked_db_unavailable`
- `activation_gate_manual_review`

Possible overall decisions:

- `controlled_inactive_preview_supported`
- `controlled_inactive_preview_supported_with_manual_overlap_review`
- `manual_overlap_review_required_before_activation`
- `defer_activation_known_elsewhere`
- `activation_gate_blocked_db_unavailable`
- `activation_gate_blocked_no_candidates`
- `manual_review_required`

## Boundary

S2N does not:

- register Finanz Informatik in the ingestion runner
- create a search profile
- write to Bronze
- approve recurring ingestion
- approve broad all-job ingestion
- persist raw HTML

A positive S2N result only supports the next discussion: whether to create a controlled inactive source-target implementation.
