# GENERIC-006 Stop-Control Evidence Repair Packet

## Purpose

GENERIC-006 turns the current GENERIC-005 stop-control blocker into an executable DB/code-backed evidence repair packet.
It does not fill evidence automatically. It diagnoses DB-backed or code-backed stop-control evidence surfaced by GENERIC-004 and tells the operator which fields must be reviewed and completed before GENERIC-005 can be rerun. It must not use CSV/Excel/export files as process input.

## Current problem addressed

The current Freeze Path is blocked because GENERIC-005 still reports `stop_control_capture_missing_or_invalid`.
The current evidence requirement row is not valid stop-control evidence: it has no company identity, keeps the placeholder evidence summary, and has no reviewer/date.

GENERIC-006 makes that state visible without guessing evidence.

## Safety boundary

GENERIC-006 is read-only and review-only:

- no database writes
- may read `stop_control_evidence_reviews` for DB-backed stop-control evidence
- no external requests
- no candidate creation
- no candidate promotion
- no gate decision writes
- no connector activation
- no scheduler changes
- no Bronze/Silver/Gold mutation
- no CSV/Excel/export file as process input

## Outputs

The runner writes:

- `exports/generic006_stop_control_capture_repair_packet/generic006_stop_control_capture_repair_packet.json`
- `exports/generic006_stop_control_capture_repair_packet/generic006_stop_control_capture_repair_packet.md`

No CSV/Excel/export assessment file is generated for process input.

## Operator sequence

1. Run GENERIC-006.
2. Model or correct DB-backed or code-backed stop-control evidence using GENERIC-008 or code review; do not use CSV/Excel/export handoffs.
3. Rerun GENERIC-005.
4. Rerun EXPAND-004.
5. Rerun EXPAND-007.
6. Only after those reports are ready, consider manual apply-gate preview design.

## Boundary note

The explicit negative/no-actionable control remains benchmark evidence only. It must not become candidate truth, gate truth, connector truth, or scheduler truth.
