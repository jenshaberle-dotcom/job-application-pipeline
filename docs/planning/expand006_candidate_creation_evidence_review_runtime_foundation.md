# EXPAND-006 Candidate Creation Evidence Review Runtime Foundation

Status: planned / patch candidate
Boundary: read-only evidence review; no candidate creation apply; no gate mutation; no connector activation.

## Purpose

EXPAND-006 turns the previous controlled candidate creation dry-run and planning anchor into an inspectable runtime review artifact.

The block should answer one question before any apply gate exists:

> Which candidate creation proposals are supported by generic evidence, which are risky because of duplicates/normalization, and which must remain stopped?

## Included runtime foundation

The additive script `scripts/run_expand006_candidate_creation_evidence_review.py` creates JSON and Markdown reports under `exports/`.

Default mode is context-only and does not inspect the database:

    python scripts/run_expand006_candidate_creation_evidence_review.py

Read-only database mode is explicit:

    python scripts/run_expand006_candidate_creation_evidence_review.py --include-db

The script must remain safe under the project freeze rules:

- no external requests
- no database writes
- no pipeline mutation
- no candidate or gate mutation
- no connector activation
- no scheduler change

## Review output

The report contains:

- current Git context
- relevant migration hints
- optional read-only database relation review
- status/count breakdowns for candidate, evidence, gate, review, origin, market, and dry-run related relations
- a hard apply boundary: `review_only_not_apply`
- next safe action: review evidence before apply gate design

## Apply boundary

This block does not create, promote, approve, reject, activate, schedule, or ingest anything.

A later apply gate must be a separate work item and requires explicit approval. Minimum requirements before that later step:

1. Dry-run candidate rows are visible in a read-only report.
2. Each candidate has source/evidence provenance.
3. Duplicate and normalization risk is reviewed.
4. The generik proof matrix has no candidate-specific shortcut.
5. The apply step remains a separate command with explicit approval.

## System impact

Affected layers:

- Discovery: helps evaluate whether observed market/company evidence can become candidate creation input.
- Evidence: exposes provenance and weak-evidence gaps.
- Candidate/Gate: review only; does not mutate candidates or gates.
- UI/Observability: creates a report shape that can later feed Review Queue cards.

Not affected:

- Bronze/Silver/Gold writes
- source registration
- connector activation
- scheduler
- external network access

## Validation

Required validation before commit:

    python -m pytest -q tests/test_expand006_candidate_creation_evidence_review.py
    python scripts/run_expand006_candidate_creation_evidence_review.py
    python scripts/run_validate001_unified_validation.py --profile commit
    git diff --check
