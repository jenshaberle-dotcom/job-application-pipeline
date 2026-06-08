# Operations Current Truth

Status: current truth

Operational work is CLI-first and deliberately boring. The goal is reliable
changes, not clever terminal tricks.

Current operator entry points:

- `../guides/operator-runbook.md`
- `../guides/development-workflow.md`
- `../guides/testing.md`
- `../reference/operations/db_migration_tracking.md`
- `../reference/operations/windows_scheduler_watchdog.md`

Workflow rule: commit, PR, merge and cleanup blocks should remain stable across
chats and handovers. Merge blocks must derive the PR number automatically from
the current feature branch instead of requiring manual `<PR_NUMBER>` replacement.
