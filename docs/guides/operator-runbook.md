# Operator runbook

Use the [Windows guide](jap_control_center_windows_app.md) for an installed app and
[development workflow](development-workflow.md) for repository changes.

## Start and inspect

The installed Windows host reads `current.json` and runs the immutable product bundle
through its WSL bridge. Private `.env`, approved documents and PostgreSQL remain local.
Use the app's installed identity and `/app-info.json` to inspect `source_revision`;
a checkout's version file does not identify the running application.

For source-development operation, inspect the launcher contract before starting:

```bash
sed -n '1,160p' scripts/run_jap_windows_control_center.sh
```

The interactive product endpoint is `127.0.0.1:8780`. A remote demo requires its own
explicit access and privacy boundary; it is not the standard installed topology.

## Update and recovery

Let the installed updater stage and verify immutable assets before consent. If an update
fails, retain logs, `current.json` and the pending/accepted target identity. The updater
owns rollback of desktop, runtime and install metadata together. Do not repair an installed
release by fetching new code into its immutable runtime directory.

Use `Stop-JAP-Control-Center.ps1` for the installed stop path. Verify process/runtime identity
before restarting; a slow response alone does not prove a failed process.

## Product actions

Read-only inspection does not authorize activation, provider calls or DB apply. The generic
assessment command exposes its actual current options through:

```bash
python scripts/run_product_v1_assessment_cohort.py --help
```

Review selected jobs, targets, effect boundaries and current DB evidence before using apply.
A result proves acceptance only when its normal product postconditions pass. Do not infer a
filled Top 5 from a published package or an old cohort report.

## Validation and unknown state

```bash
python scripts/run_validate001_unified_validation.py --profile commit
```

Classify missing evidence as `unknown`, `stale`, `inconsistent` or `needs_inspection`.
Preserve failure evidence and change a relevant precondition before retrying.
`exports/` is review output only, never pipeline input or restart authority.

PR merging uses the canonical workflow, which derives the PR identity from the branch;
manual `<PR_NUMBER>` replacement is avoided. No ZIP/chat handoff is required to inspect a repo.
