# VALIDATE-001A Unified Validation Command

Status: Current validation contract
Boundary: Read-only local validation

## Purpose

`VALIDATE-001A` is the current local validation entry point before commit, PR,
merge-readiness, and repo-backed operator decisions.

It does not create or validate generated chat-continuation artifacts. It does
not run NEXT restart steering. It does not treat exports, assistant memory,
generated summaries or chat artifacts as project truth.

## Supported profiles

| Profile | Purpose | Includes full pytest |
|---|---|---|
| `quick` | Compile active tooling, run active tooling contract tests, validate rules index and diff hygiene. | no |
| `commit` | `quick` plus full `pytest -q`. | yes |

The former restart-artifact profile is retired and must not be used.

## Required command

```bash
python scripts/run_validate001_unified_validation.py --profile commit
```

## Scope

Validation remains read-only:

- no database writes
- no scheduler changes
- no candidate, gate, connector, Bronze, Silver or Gold mutation
- no external requests
- no generated chat-continuation artifact generation

## Relationship to continuation

Until MCP reaches sufficient maturity, continuation across chats still requires a
fresh full-repository ZIP and direct repository inspection.

After MCP maturity is demonstrated, MCP-backed repo/DB state inspection replaces
the temporary full-ZIP bridge.

The retired chat-continuation mechanism does not return.
