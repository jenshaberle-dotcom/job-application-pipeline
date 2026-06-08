# INSPECT-001A Repo/DB/Docs Inspection Bundle

INSPECT-001A provides a compact, read-only inspection bundle for the current
repository state. It complements the STATE-001 project state snapshot by adding
a broader Repo/DB/Docs view without becoming an MCP server or a wider
engineering operating system.

## Purpose

The bundle is intended as a lightweight handover and pre-patch anchor:

- summarize Git state
- check expected documentation structure
- check expected tooling anchors
- summarize migration file visibility
- optionally inspect expected database relations in a read-only transaction
- write compact JSON and Markdown reports under `exports/`

## Safety boundary

The inspection bundle is intentionally read-only.

It must not:

- perform external network requests
- write to the database
- mutate candidates, gates, connectors, Bronze/Silver/Gold, scheduler, or UI state
- activate sources or run crawlers
- create commits, pull requests, or merges

## Usage

Default run without database access:

```bash
python scripts/run_inspect001_repo_db_docs_bundle.py
```

Optional database inspection requires a DSN in one of:

- `JOB_PIPELINE_DATABASE_URL`
- `DATABASE_URL`
- `POSTGRES_DSN`

Then run:

```bash
python scripts/run_inspect001_repo_db_docs_bundle.py --include-db
```

The database check opens a transaction and explicitly sets it to read-only before
checking expected public relations.

## Outputs

The script writes:

```text
exports/inspect001_repo_db_docs_bundle_<timestamp>.json
exports/inspect001_repo_db_docs_bundle_<timestamp>.md
```

## Status model

The report distinguishes:

- `pass` — expected signal is present
- `warn` — inspection completed but expected anchors are missing or incomplete
- `unavailable` — inspection could not be performed, for example because no DSN exists
- `skipped` — intentionally not executed, for example DB checks without `--include-db`

Warnings are not automatically failures. They are decision inputs for the next
safe action and for handover quality.
