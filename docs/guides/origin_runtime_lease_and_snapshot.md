# Origin runtime lease, snapshot and checkpoint recovery

## Purpose

The private GitHub origin benchmark must survive the local Windows workstation
returning to sleep. The runtime therefore combines four controls:

1. **Remote wake** – the private dispatcher wakes the workstation through the
   existing WARP → FRITZ WireGuard path.
2. **Fail-safe runtime lease** – the GitHub runner owns a PostgreSQL
   session-level advisory lock and sends a heartbeat every 20 seconds.
3. **Immutable snapshot execution** – the complete bounded projection is read
   once, fingerprint-verified and then processed without further database reads.
4. **Candidate checkpoint recovery** – every completed company result is written
   atomically and restored on an exact pipeline-ref/fingerprint retry.

The design remains `review_output_only_not_pipeline_input`. It does not write to
candidate tables, activate a source, register a connector or change a scheduler.

## Why the lease is fail-safe

The lease is a session-level PostgreSQL advisory lock. It disappears automatically
when the GitHub process exits, the connection fails or the runner is destroyed. A
local Windows watcher observes the lock and calls `SetThreadExecutionState` only
while the lock exists, plus a 90-second bounded grace period.

A crashed workflow therefore cannot leave the workstation awake indefinitely.

## One-time Windows installation

Run from a Windows PowerShell terminal in the repository root after the feature is
merged and the local checkout is updated:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install_windows_origin_runtime_lease_watcher.ps1
```

The installer:

- uses `.venv\Scripts\python.exe`,
- reads the existing local `.env` database settings,
- creates the scheduled task `Job Pipeline Runtime Lease Watcher`,
- starts it immediately,
- restarts it after transient failures.

No GitHub or Tavily secret is copied into the task. The watcher only needs local
PostgreSQL connectivity and read visibility on `pg_locks`.

## Verification

Check the task:

```powershell
Get-ScheduledTask -TaskName "Job Pipeline Runtime Lease Watcher"
```

Run one foreground observation without changing the task:

```powershell
.\.venv\Scripts\python.exe -m scripts.watch_origin_runtime_lease --env-file .env --once
```

During a private benchmark the GitHub summary should show:

```text
origin_runtime_lease=ready
Database reads after verified snapshot: 0
Runtime lease: PostgreSQL advisory lock, fail-safe on disconnect
```

## Recovery behavior

The checkpoint cache key is bound to both the exact pipeline commit and projection
fingerprint. A retry can only reuse a checkpoint when the company order and
fingerprint match exactly. Completed company results are skipped. A different
projection is rejected rather than mixed with previous evidence.

The current checkpoint granularity is one completed company. A failure inside one
company can repeat that company's provider queries, but completed companies are
not repeated.

## Re-wake boundary

The initial remote dispatcher remains the wake authority. Once the projection is
verified, the provider phase is independent of the local workstation. A second
wake during Tavily execution is therefore unnecessary. Future local write-back
phases must obtain a new wake and a new lease rather than extending this read-only
benchmark implicitly.
