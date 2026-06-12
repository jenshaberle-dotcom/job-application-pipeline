# EXPAND-007 Controlled Candidate Creation Apply-Gate Readiness

Boundary: apply-gate readiness review only; no candidate creation execution; no gate mutation; no connector activation; no scheduler change.

## Purpose

EXPAND-007 consumes the EXPAND-004 controlled candidate creation dry-run manifest and the EXPAND-006 candidate creation evidence review to decide whether a separate manual apply-gate design may be started.

It does **not** create candidates. It deliberately keeps candidate creation execution blocked and reports whether the preconditions for a future apply-gate design are met.

## Required preconditions

A future apply-gate design may only be considered when all of these are true:

- EXPAND-004 status is `ready_for_operator_candidate_creation_dry_run_review`.
- EXPAND-004 selected at least one candidate creation dry-run item.
- GENERIC-005 / GENERIC-001 final proof gaps are closed.
- EXPAND-006 evidence review has DB-inspectable signal.
- Duplicate and normalization risk can be reviewed per selected candidate.
- The future write scope is exact, explicit, dry-run-first, and operator-approved.

## Current expected result on the 2026-06-12 full export

The current full export is expected to remain blocked because the available reports show:

- EXPAND-004 overall status: `blocked_by_generic005_final_rerun`.
- selected candidate creation dry-run count: `0`.
- remaining generic proof gaps: `no_actionable_evidence_coverage`, `negative_control_coverage`.
- EXPAND-006 review signal: `context_only` / not DB-inspectable when the database is unavailable.

This is a useful product result, not a failure: the pipeline now explains why candidate creation must not proceed yet.

## Outputs

The runner writes:

- `exports/expand007_controlled_candidate_creation_apply_gate_readiness/expand007_controlled_candidate_creation_apply_gate_readiness.json`
- `exports/expand007_controlled_candidate_creation_apply_gate_readiness/expand007_controlled_candidate_creation_apply_gate_readiness.md`
- `exports/expand007_controlled_candidate_creation_apply_gate_readiness/expand007_candidate_apply_gate_readiness.csv`

The CSV is a human review artifact only. It must not become a pipeline input or activation gate dependency.

## System impact check

- Discovery: no change.
- Evidence: reads existing review artifacts only.
- Candidate/Gate: no mutation; readiness report only.
- Connector: no build, registration, or activation.
- Bronze/Silver/Gold: no reads or writes by EXPAND-007 itself.
- UI/Observability: creates a future-friendly review artifact for UI action design.

## Next action

If EXPAND-007 reports blocked status, close the listed generic proof and evidence-review blockers before designing EXPAND-008 candidate creation apply mechanics.

If EXPAND-007 reports ready status, design the future apply gate as a separate dry-run-first implementation with explicit operator approval and exact candidate-key scope.
