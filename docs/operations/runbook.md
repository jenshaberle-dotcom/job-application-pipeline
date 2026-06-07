# Operator Runbook

Status: current truth candidate
Scope: local development, validation, PR workflow, and safe operation
Last rebaseline: DOC-001F

## Purpose

This runbook contains the standard operator commands for the local project.

It is intentionally practical. Architecture belongs in `docs/architecture/`.
Governance belongs in `docs/governance/`.

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

## Branch guard

Do not work directly on `main`.

```bash
INTENDED_BRANCH="feature/descriptive-branch-name"
CURRENT_BRANCH="$(git branch --show-current)"

if [ "$CURRENT_BRANCH" = "main" ]; then
  echo "oh noes, it's main — switching to $INTENDED_BRANCH"
  git switch "$INTENDED_BRANCH" 2>/dev/null || git switch -c "$INTENDED_BRANCH"
elif [ "$CURRENT_BRANCH" != "$INTENDED_BRANCH" ]; then
  git switch "$INTENDED_BRANCH" 2>/dev/null || git switch -c "$INTENDED_BRANCH"
fi
```

## Standard validation

Run before commit and before/after merge:

```bash
python -m pytest -q
git diff --check
git status --short
```

For governance/doc changes:

```bash
python scripts/check_governance_drift.py --json
python scripts/check_governance_drift.py --strict --json || true
```

Strict mode may still be advisory depending on the current DOC/GOV phase.

## Commit workflow

```bash
git add <files>

git diff --cached --check
git diff --cached --stat

git commit -m "<clear message>"
```

## PR workflow

```bash
git push -u origin <branch>

gh pr create   --title "<PR title>"   --body "<PR body>"
```

## Merge and cleanup workflow

```bash
gh pr merge --squash --delete-branch

git switch main
git pull --ff-only

git branch --delete <branch> 2>/dev/null || true
git fetch --prune

python -m pytest -q

git status --short
git log --oneline -5
```

## Handling generated exports

`exports/` is ignored by git.

Generated reports are useful for review and handover, but they are not pipeline
inputs and are not committed by default.

## Dry-run before apply

For mutating scripts, prefer:

```bash
python -m scripts.<agent_or_command> --dry-run
```

Only use apply/write actions after reviewing the dry-run output.

If a script supports explicit write flags, the flag should be visible in the
command and PR validation.

## Pipeline safety boundaries

Do not use normal workflow commands to:

- activate a source without explicit approval gates,
- register a connector without validation and approval,
- bypass safety/legal/access stops,
- reset active controlled candidates by default,
- convert reports into hidden inputs,
- edit applied migrations.

## Documentation safety boundaries

During DOC-001:

- `docs/planning/` is historical by default,
- `docs/source_analysis/` is historical/reference by default,
- `docs/project_state/` is handover context, not Current Truth,
- `exports/` is runtime/report output,
- ADRs require rebaseline before large edits,
- obsolete docs should be archived/deprecated or rewritten, not patched into hybrids.

## Common documentation commands

Inspect documentation inventory:

```bash
python scripts/inspect_documentation_rebaseline.py   --write-report   --json   --label doc001_current
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
`docs/project_state/` out of commits unless intentionally promoted.
