# Development Workflow

Status: current guide

## Commit block

```bash
cd ~/projects/job-application-pipeline
source .venv/bin/activate

INTENDED_BRANCH="feature/<descriptive-name>"
CURRENT_BRANCH="$(git branch --show-current)"

if [ "$CURRENT_BRANCH" = "main" ]; then
  echo "oh noes, it's main — switching to $INTENDED_BRANCH"
  git switch "$INTENDED_BRANCH" 2>/dev/null || git switch -c "$INTENDED_BRANCH"
elif [ "$CURRENT_BRANCH" != "$INTENDED_BRANCH" ]; then
  git switch "$INTENDED_BRANCH"
fi

python -m pytest -q
git diff --check

git add <explicit-files>
git diff --cached --check
git diff --cached --stat
git commit -m "<message>"
```

## PR block

```bash
git push -u origin feature/<descriptive-name>

gh pr create \
  --title "<title>" \
  --body "<body>"
```

## Merge + cleanup block

```bash
cd ~/projects/job-application-pipeline
source .venv/bin/activate

git switch feature/<descriptive-name>

PR_NUMBER="$(gh pr view --json number --jq '.number')"
echo "Merging PR #$PR_NUMBER"

gh pr merge "$PR_NUMBER" --squash --delete-branch

git switch main
git pull --ff-only
git fetch --prune

git branch --delete feature/<descriptive-name> 2>/dev/null || true

python -m pytest -q
git status --short
git log --oneline -5
```

## Stability rule

Do not use manual `<PR_NUMBER>` placeholders in merge blocks. Do not introduce
surprise workflow variants in handovers. Avoid `set -euo pipefail` in user-pasted
operational blocks when a recoverable CLI error could close the terminal.
