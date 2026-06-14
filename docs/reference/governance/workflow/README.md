# Workflow Governance Reference

Status: Current Truth
Boundary: Workflow / Validation / Repo Truth

## Current workflow rule

After CONSISTENCY-001A, generated chat-continuation artifacts are not project
truth and are not workflow steering.

The former chat-continuation/NEXT restart path has been retired and archived as
a bad idea / anti-pattern under:

- `../../archive/governance/retired-chat-continuation/chat_continuation_retired_bad_idea.md`

Current active workflow references:

- `validate001_unified_validation_command.md` — local validation before commit or PR decisions.
- `inspect001_repo_db_docs_bundle.md` — read-only inspection bundle.
- `rules001_project_rules_index.md` — compact rule anchor validation.

Continuation rule:

- Use direct repository inspection.
- Use a fresh full-repository ZIP only as the temporary bridge until MCP maturity.
- Replace the ZIP bridge with MCP-backed state only after MCP reaches sufficient maturity.
- Do not create or trust generated chat-continuation artifacts again.
