# Operator Runbook

Status: Current Truth
Boundary: Local operation / recovery

## Standard workflow

Use `development-workflow.md` for commit, PR, merge and cleanup blocks.

The former chat-continuation/NEXT restart path is retired. Do not create or
trust generated chat-continuation artifacts as project truth.

Current continuation rule:

1. Directly inspect repository state.
2. Use fresh full-repository ZIP review as the temporary bridge while MCP is not mature.
3. Replace ZIP review only after MCP-backed repo/DB state inspection is proven reliable.
4. Never reintroduce generated chat-continuation artifacts as steering.

## Validation

Before commit or PR readiness:

```bash
python scripts/run_validate001_unified_validation.py --profile commit
```

## Recovery

If state is unclear, stop and classify it as one of:

- `unknown`
- `stale`
- `inconsistent`
- `needs_inspection`

Do not infer a clean state from missing evidence.

## Export boundary

`exports/` is review output only. Export artifacts must not become pipeline input,
gate input, activation prerequisite, restart truth or source of truth.

## PR merge safety note

Manual `<PR_NUMBER>` replacement is intentionally avoided. Use the canonical
development workflow in `development-workflow.md`, which derives the pull request
number from the current branch with `gh pr view --json number --jq '.number'`.

Retired chat-continuation or handover artifacts must not be used as restart
truth or next-work steering.

## PR number handling

The phrase manual `<PR_NUMBER>` replacement is kept here only as a governance
test anchor: manual replacement is explicitly avoided. Use
`development-workflow.md`, which derives the PR number from the current branch.
