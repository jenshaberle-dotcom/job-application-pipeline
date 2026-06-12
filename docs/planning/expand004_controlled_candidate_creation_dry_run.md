# EXPAND-004 Controlled Candidate Creation Dry-Run

Status: read-only implementation step after GENERIC-005.

## Purpose

EXPAND-004 turns the passed GENERIC-001 / GENERIC-005 proof chain into a small preview-only candidate creation manifest.

The goal is not to create candidates yet. The goal is to verify that the pipeline can translate generic benchmark evidence into an explainable, bounded employer-origin candidate creation preview without special-casing individual companies.

## Required precondition

EXPAND-004 may select candidate creation dry-run items only when GENERIC-005 reports:

- `overall_status = passed_all_generics_checks_review_artifact_only`
- nested GENERIC-001 final rerun status `passed_review_artifact_only`
- no remaining final GENERIC-001 gap ids
- at least one explicit positive control key
- at least one explicit negative/no-actionable control key

If this precondition is not met, EXPAND-004 must report `blocked_by_generic005_final_rerun` and must select zero candidate creation dry-run items.

## Safety boundary

EXPAND-004 is review-artifact-only:

- no database reads or writes
- no candidate creation or promotion
- no gate decisions
- no connector activation
- no scheduler mutation
- no Bronze/Silver/Gold mutation
- no external requests

The output is a dry-run manifest. Any real write requires a later explicit apply gate with visible selected targets.

## Selection rules

The dry-run manifest may select only a small, representative subset from EXPAND-003 review artifacts:

- strong detail candidates may become preview candidate records after a future operator apply gate
- strong origin/provider candidates may become preview candidate shells that still require detail follow-up
- weak-only candidates remain stop-only observations
- negative/no-actionable controls remain stop-only controls

Weak-only or negative controls must never be selected for candidate creation.

## Output

The runner writes:

- `exports/expand004_controlled_candidate_creation_dry_run/expand004_controlled_candidate_creation_dry_run.json`
- `exports/expand004_controlled_candidate_creation_dry_run/expand004_candidate_creation_dry_run_manifest.csv`
- `exports/expand004_controlled_candidate_creation_dry_run/expand004_controlled_candidate_creation_dry_run.md`

## How to run

```bash
python scripts/run_generic001_pipeline_generics_proof_gate.py
python scripts/run_generic002_benchmark_gap_closure_plan.py
python scripts/run_generic003_benchmark_control_rerun_review.py
python scripts/run_generic004_stop_control_evidence_capture_plan.py
python scripts/run_generic005_stop_control_final_rerun.py
python scripts/run_expand004_controlled_candidate_creation_dry_run.py
```

## Decision boundary

EXPAND-004 does not authorize broad candidate creation, Wave Search scaling, scheduler changes, connector activation, or TOP5 product claims.

A ready EXPAND-004 manifest only authorizes the next explicit product decision: whether to design a separate apply-gated candidate creation preview for the selected dry-run items.
