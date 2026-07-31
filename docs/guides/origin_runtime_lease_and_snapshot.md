# Origin runtime lease, snapshot and checkpoint recovery

## Purpose

The private GitHub origin benchmark must survive the local Windows workstation
returning to sleep. The runtime therefore combines six controls:

1. **Remote wake** – the private dispatcher wakes the workstation through the
   existing WARP → FRITZ WireGuard path.
2. **Fail-safe runtime lease** – the GitHub runner owns a PostgreSQL
   session-level advisory lock and sends a heartbeat every 20 seconds.
3. **Bounded local transport recovery** – the Windows watcher starts the configured
   WSL distribution when necessary and may start or restart only `tailscaled`.
4. **Awake-time telemetry** – regular watcher heartbeats are counted as observed
   awake time; long gaps are recorded separately rather than being counted awake.
5. **Immutable snapshot execution** – the complete bounded projection is read
   once, fingerprint-verified and then processed without further database reads.
6. **Candidate checkpoint recovery** – every completed company result is written
   atomically and restored on an exact pipeline-ref/fingerprint retry.

The design remains `review_output_only_not_pipeline_input`. It does not write to
candidate tables, activate a source, register a connector or change a scheduler.

## Why the lease is fail-safe

The lease is a session-level PostgreSQL advisory lock. It disappears automatically
when the GitHub process exits, the connection fails or the runner is destroyed. A
local Windows watcher observes the lock and calls `SetThreadExecutionState` only
while the lock exists, plus a 90-second bounded grace period.

A crashed workflow therefore cannot leave the workstation awake indefinitely. The
Tailscale recovery path never acquires the Windows wake lock by itself. It can make
the local transport available after a resume, but Windows remains free to sleep
whenever no runtime lease or grace period is active.

## Bounded Tailscale recovery

The watcher treats three consecutive database connection failures as a signal to
inspect the local WSL/Tailscale path. It records the WSL state before starting the
distribution, then checks:

- the `tailscaled` systemd service,
- the `tailscale0` interface,
- `BackendState` and local online state from `tailscale status --json`.

The permitted recovery actions are intentionally narrow:

1. start the configured WSL distribution through the read-only inspection call,
2. start `tailscaled` when the service is inactive,
3. restart `tailscaled` once when the service is active but the backend or
   interface remains unhealthy.

Recovery has a 10-minute cooldown and a maximum of three attempts per hour.
`NeedsLogin`, logout and machine-approval states are fail-closed. The watcher does
not run `tailscale up`, does not use an auth key, does not log out and does not
delete `/var/lib/tailscale/tailscaled.state`.

The exact service action runs through WSL as root but is fixed to:

```text
systemctl start tailscaled
systemctl restart tailscaled
```

It does not start Docker or PostgreSQL and does not execute an arbitrary shell
command as root.

## Awake-time telemetry

The watcher writes two local files:

```text
.runtime/origin-runtime-watcher.jsonl
.runtime/origin-runtime-watcher-state.json
```

The JSONL file contains only low-volume lifecycle, gap, summary and recovery
events. The state file contains the current daily and cumulative counters.
Important fields are:

- `observed_awake_seconds` – intervals between regular watcher heartbeats,
- `lease_active_seconds` – observed awake intervals during an active runtime lease,
- `awake_without_lease_seconds` – observed awake intervals without a lease,
- `suspend_or_unobserved_seconds` – gaps longer than 30 seconds,
- `tailscale_recovery_attempts`, `successes` and `failures`.

The measurement is deliberately conservative. A long gap may represent Windows
sleep, reboot, watcher pause or a stopped task, so it is called
`suspend_or_unobserved`; it is never silently counted as awake time. Consequently,
`observed_awake_seconds` is a lower-bound measurement, suitable for detecting
whether the machine appears to run continuously without claiming exact operating
system power accounting.

`awake_without_lease_seconds` is not automatically an error because the operator
may be using the workstation normally. It shows how much observed awake time was
not caused by the pipeline lease.

Inspect the current totals:

```powershell
Get-Content .\.runtime\origin-runtime-watcher-state.json
```

Inspect recent lifecycle and recovery events:

```powershell
Get-Content .\.runtime\origin-runtime-watcher.jsonl -Tail 30
```

## One-time Windows installation

Run from a Windows PowerShell terminal in the repository root after the feature is
merged and the local checkout is updated:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install_windows_origin_runtime_lease_watcher.ps1
```

Re-running the installer safely replaces the existing scheduled-task definition
and starts the updated watcher immediately.

The installer:

- uses `.venv\Scripts\python.exe`,
- reads the existing local `.env` database settings,
- uses the WSL distribution `Ubuntu` unless another name is supplied,
- creates the scheduled task `Job Pipeline Runtime Lease Watcher`,
- creates the local `.runtime` telemetry paths,
- starts the watcher immediately,
- restarts it after transient failures.

No GitHub, Tailscale auth or Tavily secret is copied into the task. The watcher
only needs local PostgreSQL connectivity and read visibility on `pg_locks`.

To select another distribution:

```powershell
powershell -ExecutionPolicy Bypass `
  -File .\scripts\install_windows_origin_runtime_lease_watcher.ps1 `
  -WslDistro "Ubuntu-24.04"
```

## Verification

Check the task:

```powershell
Get-ScheduledTask -TaskName "Job Pipeline Runtime Lease Watcher"
```

Run one foreground observation without changing the task:

```powershell
.\.venv\Scripts\python.exe -m scripts.watch_origin_runtime_lease `
  --env-file .env `
  --once
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
