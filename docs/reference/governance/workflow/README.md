# Workflow and Tooling Contracts

Status: reference navigation
Scope: standardized local engineering workflow and handover tooling

This directory groups the small Tooling/Governance contracts that support the
local project workflow. They are intentionally kept out of the `docs/reference/`
root so the reference root remains a domain navigation layer instead of a mixed
bag of standalone process files.

## Contracts

- `handover001_standard_chat_handover_contract.md` — standard chat handover contract.
- `inspect001_repo_db_docs_bundle.md` — read-only repository, database and documentation inspection bundle.
- `rules001_project_rules_index.md` — compact active rules and backlog-boundary index.
- `validate001_unified_validation_command.md` — unified validation command before commit or PR decisions.
- `next001_next_safe_action_report.md` — next-safe-action orientation after validation, merge, cleanup, or handover.

## Boundary

These contracts support the engineering workflow. They do not define product
pipeline behavior, connector activation, source relevance, or candidate/gate
state transitions.
