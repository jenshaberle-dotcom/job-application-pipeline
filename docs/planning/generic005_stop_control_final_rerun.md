# GENERIC-005 Stop-Control Evidence / GENERIC-001 Final Rerun

Status: planned/read-only implementation step after GENERIC-004.

## Purpose

GENERIC-005 is the executable bridge from DB-backed or code-backed stop-control evidence back into the GENERIC-001 proof gate.

It validates explicit operator stop-control evidence and reruns GENERIC-001 in memory with:

- the positive control already closed by GENERIC-003
- one explicit negative/no-actionable stop-control row from DB-backed or code-backed review evidence surfaced by GENERIC-004
- a benchmark-only augmented EXPAND-003 review artifact

The goal is to decide whether the generic benchmark can finally pass before EXPAND-004 controlled candidate creation dry-run design starts.

## Safety boundary

GENERIC-005 is review-artifact-only:

- may read `stop_control_evidence_reviews` for DB-backed stop-control evidence
- no database writes
- no candidate creation or promotion
- no gate decisions
- no connector activation
- no scheduler mutation
- no Bronze/Silver/Gold mutation
- no external requests

CSV/Excel/export rows are never accepted as stop-control evidence. DB-backed or code-backed review evidence is benchmark control evidence only; it is not pipeline truth and does not create or promote a candidate.

## Accepted stop-control evidence

A stop-control row may be accepted only when it is DB-backed or code-backed and has all of the following:

- `control_type` is `new_clean_no_actionable_negative_control` or `existing_safe_stop_negative_control`
- `required_for_gap_ids` includes both `no_actionable_evidence_coverage` and `negative_control_coverage`
- `company_key` and `company_name` are filled
- `review_action` is a safe-stop action
- `evidence_summary` describes the bounded stop-control review and is not placeholder text
- `reviewer` and `review_date` are filled
- `boundary` remains `review_artifact_only_no_candidate_or_gate_write`

Weak-only candidates remain insufficient. GENERIC-005 must not reinterpret weak-only market evidence as a negative control.

## GENERIC-008 DB-backed evidence source

The preferred operator path is `scripts/run_generic008_stop_control_evidence_registry.py`. It is dry-run by default and writes only to `stop_control_evidence_reviews` when `--write` is explicit. This DB row may then be read by GENERIC-005. No local file artifact may be edited and re-ingested.

## Output

The runner writes:

- `exports/generic005_stop_control_final_rerun/generic005_stop_control_final_rerun.json`
- `exports/generic005_stop_control_final_rerun/generic005_stop_control_final_rerun.md`
- nested GENERIC-001 final rerun artifacts under `exports/generic005_stop_control_final_rerun/generic001_final_rerun/`

## How to run

```bash
python scripts/run_generic001_pipeline_generics_proof_gate.py
python scripts/run_generic002_benchmark_gap_closure_plan.py
python scripts/run_generic003_benchmark_control_rerun_review.py
python scripts/run_generic004_stop_control_evidence_capture_plan.py
python scripts/run_generic005_stop_control_final_rerun.py
```

When no DB/code-backed stop-control evidence exists, GENERIC-005 should report `stop_control_capture_missing_or_invalid` and keep EXPAND-004 blocked.

When one valid DB-backed or code-backed stop-control row exists, GENERIC-005 may produce a nested GENERIC-001 final report with `passed_review_artifact_only`.

## Decision boundary

GENERIC-005 can unblock EXPAND-004 design only if the nested GENERIC-001 final rerun passes with no benchmark gaps.

A pass still does not authorize broad apply, Wave Search scaling, scheduler changes, connector activation, or TOP5 product claims. It only authorizes running `docs/planning/expand004_controlled_candidate_creation_dry_run.md` as a separate read-only manifest step.
