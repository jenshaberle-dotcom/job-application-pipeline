# Windows Scheduler Watchdog — Local Daily Pipeline

## Purpose

This document defines the local Windows scheduler setup for the job-application-pipeline development environment.

It is not cloud orchestration. It is a defensive local-development wrapper that keeps daily ingestion usable while the project is still running on a private Windows/WSL machine.

## Why This Exists

Windows Task Scheduler can show a successful last manual run while still missing a scheduled run when the machine was unavailable. A classic daily trigger is therefore not enough for vacation-safe operation.

The S2P scheduler setup uses two safeguards:

1. a daily trigger at the configured time
2. a logon catch-up trigger

The wrapper stores the date of the last successful run in a small state file and skips duplicate same-day executions. That means a missed overnight run can be caught on the next logon, but repeated manual or logon triggers do not create duplicate same-day pipeline runs.

## Installed Task Shape

Install or update the task from PowerShell:

```powershell
cd \wsl.localhost\Ubuntu\home\jens_h\projects\job-application-pipeline
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\install_or_update_job_pipeline_scheduler.ps1
```

The installer copies the wrapper to:

```text
%USERPROFILE%\job-pipeline-scheduler\run_scheduled_pipeline.ps1
```

and registers one task:

```text
Job Pipeline Daily Run
```

with:

- daily trigger at `02:30`
- logon catch-up trigger
- `StartWhenAvailable = true`
- `WakeToRun = true`
- duplicate instances ignored

## Manual Same-Day Run

For an intentional manual data refresh, bypass the same-day skip guard:

```powershell
& "$env:USERPROFILE\job-pipeline-scheduler\run_scheduled_pipeline.ps1" -Force
```

## State and Logs

Logs are written to:

```text
%USERPROFILE%\job-pipeline-scheduler-logs
```

The success marker is written to:

```text
%USERPROFILE%\job-pipeline-scheduler\state\daily-pipeline-state.json
```

The marker is operational state only. It is not a pipeline input, not a source-of-truth artifact and not used for database decisions.

## Boundary

This watchdog cannot run while the computer is fully powered off. Its purpose is to catch up once the machine is available again.

For cloud operation, this local scheduler must be replaced by managed orchestration such as a cloud scheduler, container job, workflow engine or CI/CD-triggered scheduled job.
