# Operations Current Truth

Status: current truth

Operational work is CLI-first and deliberately boring. The goal is reliable
changes, not clever terminal tricks.

Current operator entry points:

- `../guides/development-workflow.md` for commit, PR, merge and cleanup blocks.
- `../guides/operator-runbook.md` for local operation and recovery.
- `../guides/testing.md` for test expectations.
- `../reference/governance/workflow/validate001_unified_validation_command.md` and `scripts/run_validate001_unified_validation.py` for the unified local validation entry point.
- `../reference/governance/workflow/next001_next_safe_action_report.md` and `scripts/run_next001_next_safe_action_report.py` for next-safe-action orientation after validation, merge, cleanup, or handover.
- `../reference/operations/db_migration_tracking.md` for migration tracking.
- `../reference/operations/windows_scheduler_watchdog.md` for scheduler context.

Workflow blocks should remain stable across chats and handovers. Merge blocks
must derive the PR number automatically from the current feature branch; they
must not require manual `<PR_NUMBER>` replacement.
