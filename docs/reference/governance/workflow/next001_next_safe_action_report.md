# NEXT-001A Next Safe Action Report

Status: reference contract

NEXT-001A is the read-only orientation report for deciding what should happen
next after validation, merge, cleanup, or chat handover.

It exists because file names, chat claims, and handover summaries are not enough.
The current Git state remains the source of truth. NEXT-001A compares the actual
repository state with available validation and handover exports and then reports
the next safe action.

## Purpose

NEXT-001A should answer:

- Is the current branch clean or dirty?
- Which Tooling/Governance workflow items are present in the current Git HEAD?
- Is the latest detected handover export fresh or stale?
- Is the latest detected validation export a passing commit-profile validation?
- Should the next step be validation, PR/merge, handover refresh, another
  Tooling/Governance item, or a return to product pipeline work?

## Standard command

Run the report from the repository root:

    python scripts/run_next001_next_safe_action_report.py

The command writes JSON and Markdown reports under `exports/` and prints a short
console summary.

You can also pass explicit report files:

    python scripts/run_next001_next_safe_action_report.py \
      --handover-json exports/<handover>.json \
      --validation-json exports/<validate001>.json

If no explicit files are provided, the command tries to read the latest matching
handover and VALIDATE-001 JSON files from `exports/`.

## Safety boundary

NEXT-001A is read-only.

It must not:

- perform external network requests
- read from or write to the database
- mutate pipeline data
- change candidates, gates, sources, connectors, Bronze/Silver/Gold, scheduler,
  or UI state
- create commits, pull requests, or merges
- activate MCP-001 or any other backlog item

## Handover stale-state detection

NEXT-001A intentionally detects stale handover signals, for example:

- the handover Git HEAD does not match the current HEAD
- an item is present in HEAD but missing from `completed_work_items`
- `recommended_next` still names a Tooling/Governance item that is already
  present in HEAD

This keeps chat transitions honest: a fresh filename is not treated as proof of
a fresh project state.

## Freeze-path behavior

The standard Tooling/Governance sequence is:

1. STATE-001A Project State Snapshot Contract
2. INSPECT-001A Repo/DB/Docs Inspection Bundle
3. HANDOVER-001A Standard Chat Handover Contract
4. RULES-001A Project Rules Index
5. VALIDATE-001A Unified Validation Command
6. NEXT-001A Next Safe Action Report

MCP-001 remains backlog-only unless explicitly promoted.

After the standard sequence is present in HEAD and the repository is clean,
NEXT-001A should recommend returning to explicitly selected product pipeline work.
The current expected candidate is `SENSOR-001A BA Remote/Nationwide Coverage
Validation`.

## Output contract

The JSON report contains:

- `git`
- `documentation`
- `tooling_governance_status`
- `standard_workflow_completion`
- `validation_signal`
- `handover_signal`
- `product_return_candidates`
- `next_safe_action`
- `safety_boundary`

The Markdown report is for human review. The JSON report is the machine-readable
handover and restart surface.
