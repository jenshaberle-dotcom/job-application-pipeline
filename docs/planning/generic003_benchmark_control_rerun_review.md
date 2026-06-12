# GENERIC-003 Benchmark Control Rerun Review

Status: planned/read-only implementation step after GENERIC-002.

## Purpose

GENERIC-003 turns the GENERIC-002 closure plan into an artifact-only control rerun. It reuses the existing EXPAND-003 candidate review report and the GENERIC-002 control recommendations to rerun GENERIC-001 with explicit benchmark control metadata.

This is intentionally not an apply step. It should only answer:

- Which GENERIC-001 gaps can be closed from existing review artifacts?
- Which gaps remain blocked because benchmark evidence is still missing?
- Is it safe to design EXPAND-004 as a separate controlled dry-run?

## Current expected result

With the current EXPAND-003 benchmark and GENERIC-002 plan, the expected result is partial closure:

- `positive_control_coverage` can be closed with `adesso_business_consulting`.
- `no_actionable_evidence_coverage` remains blocked.
- `negative_control_coverage` remains blocked.

That means EXPAND-004, Wave Search scaling, scheduler changes, and TOP5 product claims must remain blocked until a clean no-actionable/negative-control stop case exists as review evidence.

## Safety boundary

GENERIC-003 is review-artifact-only:

- no database reads or writes
- no candidate creation or promotion
- no gate decisions
- no connector activation
- no scheduler mutation
- no Bronze/Silver/Gold mutation
- no external requests

## How to run

```bash
python scripts/run_generic001_pipeline_generics_proof_gate.py
python scripts/run_generic002_benchmark_gap_closure_plan.py
python scripts/run_generic003_benchmark_control_rerun_review.py
```

The script writes:

- `exports/generic003_benchmark_control_rerun_review/generic003_benchmark_control_rerun_review.json`
- `exports/generic003_benchmark_control_rerun_review/generic003_benchmark_control_rerun_review.md`
- nested GENERIC-001 after-rerun artifacts for detailed inspection

## Decision boundary

GENERIC-003 may close explicit control metadata gaps. It must not invent missing benchmark evidence. If a negative control or no-actionable stop case is missing, the correct result is a stop signal and a precise evidence request, not silent pass-through.

## Follow-up after GENERIC-003

GENERIC-004 is the next read-only step when GENERIC-003 reports the remaining gaps `negative_control_coverage` and `no_actionable_evidence_coverage`. It converts the missing safe-stop evidence into an explicit capture plan and CSV template without treating weak-only candidates as negative controls.
