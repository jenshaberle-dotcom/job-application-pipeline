# GENERIC-006 Stop-Control Capture Repair Packet

## Purpose

GENERIC-006 turns the current GENERIC-005 stop-control blocker into an executable operator repair packet.
It does not fill evidence automatically. It diagnoses the GENERIC-004 capture CSV and tells the operator which fields must be reviewed and completed before GENERIC-005 can be rerun.

## Current problem addressed

The current Freeze Path is blocked because GENERIC-005 still reports `stop_control_capture_missing_or_invalid`.
The capture template row is still a template: it has no company identity, keeps the placeholder evidence summary, and has no reviewer/date.

GENERIC-006 makes that state visible without guessing evidence.

## Safety boundary

GENERIC-006 is read-only and review-only:

- no database writes
- no database reads
- no external requests
- no candidate creation
- no candidate promotion
- no gate decision writes
- no connector activation
- no scheduler changes
- no Bronze/Silver/Gold mutation

## Outputs

The runner writes:

- `exports/generic006_stop_control_capture_repair_packet/generic006_stop_control_capture_repair_packet.json`
- `exports/generic006_stop_control_capture_repair_packet/generic006_stop_control_capture_repair_packet.md`
- `exports/generic006_stop_control_capture_repair_packet/generic006_capture_repair_assessments.csv`

## Operator sequence

1. Run GENERIC-006.
2. Fill or correct the GENERIC-004 capture CSV using the repair packet.
3. Rerun GENERIC-005.
4. Rerun EXPAND-004.
5. Rerun EXPAND-007.
6. Only after those reports are ready, consider manual apply-gate preview design.

## Boundary note

The explicit negative/no-actionable control remains benchmark evidence only. It must not become candidate truth, gate truth, connector truth, or scheduler truth.
