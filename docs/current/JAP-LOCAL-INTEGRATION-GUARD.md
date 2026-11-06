# JAP Local Safety & PoC Integration

Standalone, local Python 3.12+ tool for **JAP Classic + JAP Runtime**, designed for WSL/Linux. It does not need a server, Docker container or database access. Git SSH/HTTPS credentials on the host are used for GitHub pushes. Optional PoC integration tests use `pytest` from the invoking Python environment and the existing JAP code/dependencies.

## Design

The existing JAP Classic and Runtime checkouts remain the sources of truth. `audit` is read-only. `plan` lists candidate file paths and SHA-256 checksums for operator review without networking. `backup` creates one **orphan, code/docs/tests-only snapshot branch** in each GitHub repository; the snapshots contain the safe contents of tracked and unignored new source files, including uncommitted file edits. They do **not** carry the entire Git history or cover runtime databases, generated crawl data, candidate personal records or credentials. The GitHub repository might be public, so reviewing the files and backup scope before approval is essential. If source text contains apparent token/private-key patterns, backup stops before pushing. A successful push must be verified by matching the remote SHA.

`prepare` first performs both backups, then creates a new **local integration worktree** from the current JAP Classic HEAD. It fetches and merges the isolated Hannover Profile Market PoC into that separate worktree and runs three existing test modules. It does not change the original working tree. On a conflict or test failure it refuses to mark the integration as eligible for application. A passing integration receives a local `integration-receipt.json` with exact branch + commit SHA and test status.

`apply` is an explicit optional operation. It requires a passing receipt, same source checkout, same original branch and HEAD, and a clean working tree. The update is `git merge --ff-only` of the tested local integration branch, not a direct merge into `main` or a remote push.

## Installation

Download this package to WSL, unpack it, and run from the directory containing `local_jap_guard.py`:

```bash
python3.12 local_jap_guard.py \
  --classic "$HOME/path/to/job-application-pipeline" \
  --runtime "$HOME/path/to/job-pipeline-runtime" \
  audit
```

The `--classic` and `--runtime` paths must point to the **repository root**. Both repositories must have a GitHub `origin` that matches `jenshaberle-dotcom/job-application-pipeline` or `jenshaberle-dotcom/job-pipeline-runtime` respectively. For WSL, use Linux paths such as `/home/user/...` or `/mnt/c/...`, not Windows-style `C:\...` paths.

Before remote backup, run the no-network preview and review its path list:

```bash
python3.12 local_jap_guard.py \
  --classic "$HOME/path/to/job-application-pipeline" \
  --runtime "$HOME/path/to/job-pipeline-runtime" \
  plan
```

Look at `~/jap-poc-guard/job-application-pipeline-plan.json` and `job-pipeline-runtime-plan.json`. No files are pushed by this command. Then review the tool's `SAFE_DIRS`, `BAN_DIRS`, `SAFE_SUFFIX` and `SENSITIVE` rules. The default scope is source, docs, tests, examples and safe configuration text. Git-ignored data and runtime databases are intentionally not included.

## One-command secure backup + staged PoC

```bash
python3.12 -m pip install --user pytest  # if not already available
python3.12 local_jap_guard.py \
  --classic "$HOME/path/to/job-application-pipeline" \
  --runtime "$HOME/path/to/job-pipeline-runtime" \
  --output "$HOME/jap-poc-guard" \
  prepare --confirm BACKUP_AND_STAGE
```

Expected sequence:

1. Classic source-only snapshot branch pushed + exact remote SHA verified.
2. Runtime source-only snapshot branch pushed + exact remote SHA verified.
3. New local integration branch/worktree created from the Classic checkout's current HEAD.
4. PoC merge performed only in that worktree.
5. Existing Hannover registry, profile-expansion and role-staging tests run.
6. Local receipt contains status `staged_tested_not_applied` only on test success.

Check `~/jap-poc-guard/integration-receipt.json`, `integration-tests.log`, and the `integration-*` worktree. If the tests fail, do **not** apply; inspect the log. No Docker, DB, RCC or scheduler writes are made by the guard.

## Backup alone

```bash
python3.12 local_jap_guard.py \
  --classic "$HOME/path/to/job-application-pipeline" \
  --runtime "$HOME/path/to/job-pipeline-runtime" \
  backup --confirm BACKUP
```

Snapshot branches appear under `backup/jap-host-source-...` in **each** repository. Because they are orphan commits, do not merge them into `main`. Treat them as readable recovery snapshots of checked-in and uncommitted source content. Git history, generated result archives and databases need a separate deliberate backup process.

## Optional application to the original Classic checkout

Only after two confirmed source backups and passing staged tests, and once the original Classic working directory is **clean** and its HEAD unchanged:

```bash
python3.12 local_jap_guard.py \
  --classic "$HOME/path/to/job-application-pipeline" \
  --runtime "$HOME/path/to/job-pipeline-runtime" \
  --output "$HOME/jap-poc-guard" \
  apply --confirm APPLY
```

This updates the **local active branch** by verified fast-forward only. It does not push this integration to GitHub, modify Runtime, automatically register connectors or change production configurations. If Classic is still dirty, `apply` refuses; retain the staged worktree or manually commit/reconcile current changes before generating a fresh staged integration.

## Validation

The guard has unit tests using temporary local bare Git repositories; running them makes no external calls:

```bash
python3.12 -m unittest -v test_local_jap_guard.py
```

The integration step's tests require the PoC's code and its Python dependencies. The local machine, installed dependencies and current unpublished local JAP revisions cannot be validated remotely; actual receipts must be produced on the user's host.

### Security / recovery limits

- No `git add .`, hard reset, `git clean`, force push, automatic merge to `main` or automatic alteration of active local files.
- A GitHub push can fail due to credentials, protected branches or network connectivity; a failed backup blocks staging. If Classic succeeds but Runtime fails, the process is **partial**, and only the successful receipt should be trusted.
- Source snapshots are **not** complete system backups. The secret detector is intentionally bounded and cannot certify absence of every kind of sensitive information. Do not use this tool to publish personal application records, production credentials, raw Gmail/ATS payloads, DB dumps or proprietary data. Review the snapshot scope before committing to a public remote.
- `prepare` never overwrites or deletes local changes, even if the merge produces conflicts. `apply` requires explicit user approval after reviewing the output.
- For sensitive or proprietary data, use an encrypted private backup destination instead of a public GitHub branch. Dataset backups require explicit review and are outside the default guard scope.