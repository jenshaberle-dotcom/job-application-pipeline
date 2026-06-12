# GENERIC-004 Stop-Control Evidence Capture Plan

Status: planned/read-only implementation step after GENERIC-003.

## Purpose

GENERIC-004 closes the remaining GENERIC-003 ambiguity by turning the missing stop/negative-control evidence into a concrete operator capture plan.

GENERIC-003 can close the positive-control gap from existing EXPAND-003 evidence, but the benchmark still needs:

- one explicit `no_actionable_evidence_coverage` case
- one explicit `negative_control_coverage` case

GENERIC-004 intentionally does not reinterpret weak-only candidates as negative controls. Weak market hints show that the pipeline can avoid candidate creation from weak evidence, but they do not prove a clean no-actionable stop or known blocked control.

## Safety boundary

GENERIC-004 is review-artifact-only:

- no database reads or writes
- no candidate creation or promotion
- no gate decisions
- no connector activation
- no scheduler mutation
- no Bronze/Silver/Gold mutation
- no external requests

## Output

The runner writes:

- `exports/generic004_stop_control_evidence_capture_plan/generic004_stop_control_evidence_capture_plan.json`
- `exports/generic004_stop_control_evidence_capture_plan/generic004_stop_control_evidence_capture_plan.md`
- `exports/generic004_stop_control_evidence_capture_plan/generic004_stop_control_capture_template.csv`

The CSV template is not a pipeline input. It is an operator review template that documents the missing stop-control evidence before a later proof-gate rerun.

## How to run

```bash
python scripts/run_generic001_pipeline_generics_proof_gate.py
python scripts/run_generic002_benchmark_gap_closure_plan.py
python scripts/run_generic003_benchmark_control_rerun_review.py
python scripts/run_generic004_stop_control_evidence_capture_plan.py
```

## Expected current result

With the current EXPAND-003 benchmark:

- no eligible safe-stop candidate exists
- weak-only candidates remain explicitly not eligible as negative controls
- GENERIC-004 should produce an operator capture template
- EXPAND-004, Wave Search scaling, scheduler changes, and TOP5 product claims remain blocked

## Decision boundary

GENERIC-004 may prepare evidence capture. It must not fake benchmark closure. The next proof step may only pass once a real safe-stop/no-actionable control exists and is explicitly passed to GENERIC-001 as a negative control.

## Handoff to GENERIC-005

GENERIC-004 produces the capture template. GENERIC-005 validates the filled template, rejects placeholders or weak-only reinterpretations, and performs the GENERIC-001 final rerun as a review artifact only.

The handoff remains blocked until one explicit safe-stop/no-actionable negative control row is filled with reviewer, review date, evidence summary and the no-write boundary.
