# EXPAND-003 Result Interpretation / Candidate Review Delta Report

Status: planned implementation block  
Scope: Search Intelligence / EXPAND-002 evidence interpretation / human review queue

## Purpose

EXPAND-003 interprets the controlled EXPAND-002 external probe result artifacts and turns them into a candidate review delta report.

The goal is to move from raw external search results toward a clear, bounded human-review queue.

## Boundary

This block may:

- read an EXPAND-002 JSON review artifact
- aggregate URL-level evidence classes by company/candidate
- assign review-only actions such as `ready_for_human_evidence_review` or `weak_external_hint_no_candidate_creation`
- write JSON/CSV/Markdown review artifacts

This block must not:

- create candidates automatically
- promote candidates automatically
- write gate decisions
- activate connectors
- mutate Bronze, Silver or Gold
- write database state
- change scheduler state
- use CSV/Excel/local exports as production source of truth
- bypass human approval gates

## Interpretation policy

Strong external evidence means review priority, not gate truth.

A company may be marked as `ready_for_human_evidence_review` when company-specific job/detail evidence exists. A company may be marked as `ready_for_detail_followup_review` when origin or provider evidence exists but detail evidence is still missing or not sufficient.

Weak market or aggregator evidence must not create a candidate. It remains a learning/review signal only.

## Default command

    python scripts/run_expand003_candidate_review_delta_report.py

The default command reads the latest EXPAND-002 JSON artifact under `exports/expand002_controlled_external_probe_trial_run*`.

An explicit input path can be supplied:

    python scripts/run_expand003_candidate_review_delta_report.py --input exports/expand002_controlled_external_probe_trial_run_YYYYMMDD-HHMMSS/expand002_controlled_external_probe_trial_run.json

## Outputs

Default output directory:

    exports/expand003_candidate_review_delta_report/

Expected files:

- `expand003_candidate_review_delta_report.json`
- `expand003_candidate_review_delta_report.csv`
- `expand003_candidate_review_delta_report.md`

## Next step

A later apply/review block may let the operator inspect selected `ready_for_*` items and explicitly decide whether a company should become a real candidate or receive additional evidence repair.

That apply block must remain separate and must use dry-run before `--apply`.
