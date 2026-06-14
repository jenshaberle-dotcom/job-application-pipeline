# Operations Current Truth

Status: current truth

Operational work is CLI-first and deliberately boring. The goal is reliable
changes, not clever terminal tricks.

Current operator entry points:

- `../guides/development-workflow.md` for commit, PR, merge and cleanup blocks.
- `../guides/operator-runbook.md` for local operation and recovery.
- `../guides/testing.md` for test expectations.
- `../reference/governance/workflow/validate001_unified_validation_command.md` and `scripts/run_validate001_unified_validation.py` for the unified local validation entry point.
- `../reference/operations/db_migration_tracking.md` for migration tracking.
- `../reference/operations/windows_scheduler_watchdog.md` for scheduler context.

The former generated chat-continuation restart mechanism is retired and
archived as a bad idea. Continuity comes from direct repository inspection,
temporary full-repository ZIP review, and later MCP-backed state.

Merge blocks must derive the PR number automatically from the current feature
branch; they must not require manual `<PR_NUMBER>` replacement.
