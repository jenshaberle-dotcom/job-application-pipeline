# GENERIC-008 Stop-Control Evidence Registry

## Purpose

GENERIC-008 creates the DB-backed stop-control evidence registry required to close the remaining GENERIC benchmark gaps without CSV, Excel, Markdown, JSON export, or other file-based operator handoffs.

The registry stores one explicit operator-reviewed safe-stop / no-actionable negative-control row for benchmark proof only. It is not candidate truth, gate truth, connector truth, source activation, Bronze/Silver/Gold mutation, scheduler state, or TOP5 product evidence by itself.

## DB object

Migration `075_create_stop_control_evidence_reviews.sql` creates:

- `stop_control_evidence_reviews`
- `gold_stop_control_evidence_review_history`

Accepted rows must include:

- `control_type`: `new_clean_no_actionable_negative_control` or `existing_safe_stop_negative_control`
- `required_for_gap_ids`: includes both `no_actionable_evidence_coverage` and `negative_control_coverage`
- `company_key` and `company_name`
- safe-stop `review_action`
- explicit `evidence_summary`
- `reviewer`
- ISO `review_date`
- boundary `review_artifact_only_no_candidate_or_gate_write`

## Safety boundary

GENERIC-008 is dry-run by default. `--write` is explicit and limited to `stop_control_evidence_reviews` only.

It does not:

- ingest jobs
- create candidates
- write gate decisions
- activate connectors or sources
- write Bronze/Silver/Gold
- change scheduler configuration
- use CSV/Excel/export artifacts as input

## Operator sequence

1. Run GENERIC-004/005/006 to confirm the blocker.
2. Create a dry-run GENERIC-008 plan with explicit operator evidence.
3. Add `--write` only after the row is reviewed.
4. Rerun GENERIC-005.
5. Rerun EXPAND-004 and EXPAND-007.
6. Rerun EXPAND-008.

## Decision boundary

A GENERIC-008 row may close benchmark-control coverage only. It must not be reused as source truth, candidate truth, or application decision truth.
