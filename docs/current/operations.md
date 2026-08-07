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

## Repository-backed re-entry contract

Re-entry is not a chat handover and must not recreate the retired restart
mechanism. It is a bounded continuation from durable repository, PR, CI and
runtime truth after an external operational outage, governance/operator gate,
technical boundary or demonstrated context boundary.

### Freeze record at every bounded stop

The active PR or issue must contain one explicit re-entry record with:

- repository and canonical `main` SHA;
- active branch, exact head SHA, issue and PR number;
- required CI run IDs and a per-job result matrix;
- completed implementation and validation evidence that must not be repeated;
- the classified stop reason: external operational, governance/operator,
  technical or context boundary;
- all side effects that remain prohibited;
- one exact next safe action and its preconditions.

The record is evidence, not authority over newer repository truth.

### Re-entry sequence

1. Inspect the repository, current `main`, branch head, PR state, review threads,
   required checks and the external dependency that caused the stop.
2. Compare live truth with the freeze record and classify drift:
   `no_drift`, `main_drift`, `head_drift`, `pr_drift`, `ci_drift` or
   `runtime_truth_drift`.
3. Preserve completed evidence only when it belongs to the unchanged head SHA.
   Do not repeat successful jobs or product mutations merely to recreate a
   previous narrative.
4. When the head is unchanged and failure was infrastructure-only, rerun only
   the missing, cancelled or infrastructure-failed job after the external
   incident is resolved.
5. When the head changed, old CI is no longer merge authority: run the complete
   required CI suite on the new head. When `main` changed, re-check
   mergeability, resolve drift safely and then run complete required CI.
6. Before any product-side continuation, inspect database and audit truth first.
   Never activate a source, register a connector, ingest data or replay another
   mutation as a re-entry shortcut.
7. Merge only when every required check is green for the exact current head.
   After merge, verify canonical `main`, the merge SHA, post-merge CI and issue
   closure.

A re-entry record may identify the next safe action, but it never loosens a
gate, converts unknown state to success or authorizes a side effect.
