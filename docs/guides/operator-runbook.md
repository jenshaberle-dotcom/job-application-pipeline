# Operator Runbook

Status: current guide
Scope: local operation, safety checks and recovery

## Purpose

This runbook keeps operational commands in one practical place. Architecture
belongs in `docs/current/`; stable technical detail belongs in `docs/reference/`.

The standard commit, PR, merge and cleanup workflow is intentionally maintained
in `development-workflow.md` to avoid diverging command variants.

## Local setup

```bash
cd ~/projects/job-application-pipeline
source .venv/bin/activate
```

Check branch and status:

```bash
git branch --show-current
git status --short
```

## Standard workflow

Use `development-workflow.md` for the canonical blocks:

- Commit block
- PR block
- Merge + cleanup block
- optional handover export block

Rules that must not drift:

- no commits on `main`,
- no `git add .`,
- no manual `<PR_NUMBER>` replacement in merge blocks,
- no surprise workflow variants between chat, handover and docs,
- no `set -euo pipefail` in user-pasted recovery-prone blocks.

## Standard validation

Run before commit and after merge:

```bash
python -m pytest -q
git diff --check
git status --short
```

For governance or documentation changes:

```bash
python scripts/check_documentation_architecture.py --json
python scripts/check_documentation_references.py --write-report --json
python scripts/check_adr_rebaseline.py --json
python scripts/check_governance_drift.py --strict
```

## Dry-run before apply

For mutating scripts, prefer:

```bash
python -m scripts.<agent_or_command> --dry-run
```

Only use apply/write actions after reviewing the dry-run output. If a script
supports explicit write flags, the flag should be visible in the command and PR
validation.

## Pipeline safety boundaries

Do not use normal workflow commands to:

- activate a source without explicit approval gates,
- register a connector without validation and approval,
- bypass safety/legal/access stops,
- reset active controlled candidates by default,
- convert reports into hidden inputs,
- edit applied migrations.

## Documentation safety boundaries

- `docs/current/` is small current truth.
- `docs/reference/` is stable detail, not a second product story.
- `docs/planning/` is active planning only.
- `docs/archive/` is historical by default.
- `exports/` is report and handover output, not pipeline input.
- New docs should normally update an existing artifact before creating another file.

## Common documentation commands

Inspect documentation inventory:

```bash
python scripts/inspect_documentation_rebaseline.py --write-report --json --label doc001_current
```

Refresh archive indexes:

```bash
python scripts/build_documentation_archive_index.py --check
python scripts/build_documentation_archive_index.py
```

Check governance drift:

```bash
python scripts/check_governance_drift.py --json
```

## What to do when a patch fails

Stop and inspect. Do not force apply.

Useful commands:

```bash
git status --short
git diff --stat
git diff --check
git branch --show-current
```

If the failure is a context conflict, prefer a state-specific follow-up patch or
a Python file-writer over manual partial application.

## What to do before a chat handover

Prefer ending with:

- clean commit,
- PR merged,
- branch cleanup done,
- tests green,
- current ZIP available if further code work depends on repo state.

If a handover is needed mid-block, export concise state under `exports/` and keep
`exports/project_state/` out of commits unless intentionally promoted.
