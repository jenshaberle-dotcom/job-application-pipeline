# Origin runtime lease, snapshot and checkpoint recovery

## Purpose

The private GitHub origin benchmark must survive the local Windows workstation
returning to sleep. The runtime combines six controls:

1. **Remote wake** – the private dispatcher wakes the workstation through the
   WARP → FRITZ WireGuard path.
2. **Fail-safe runtime lease** – the GitHub runner owns a PostgreSQL advisory lock.
3. **Bounded local Tailscale recovery** – the Windows watcher may start or restart
   only the WSL `tailscaled` service.
4. **Awake-time telemetry** – regular watcher intervals are counted as observed
   awake time; long gaps are kept separate.
5. **Immutable snapshot execution** – the bounded projection is fingerprinted and
   processed without later database reads.
6. **Candidate checkpoint recovery** – completed company results are restored only
   for the exact pipeline-ref and projection fingerprint.

The design remains `review_output_only_not_pipeline_input`. It does not write to
candidate tables, activate a source, register a connector or change a scheduler.

## Deployed topology

The production workstation uses this path:

```text
Windows Scheduled Task
→ %LOCALAPPDATA%\JobPipelineRuntimeLeaseWatcher\origin-runtime-lease-watcher.ps1
→ wsl.exe -d Ubuntu
→ ~/projects/job-application-pipeline
→ local PostgreSQL and Tailscale in WSL
```

The watcher is deliberately copied outside the repository so that it can run as a
hidden Windows task while the source repository and Python virtual environment
remain in WSL. It does not require Windows Python and does not copy the database
`.env` file to Windows.

## Fail-safe wake-lock behavior

The GitHub runtime lease is a session-level PostgreSQL advisory lock. It disappears
when the runner exits or loses its database connection. The Windows watcher calls
`SetThreadExecutionState` only while the lease is active, plus a 90-second grace
period.

Tailscale inspection or recovery does not acquire the Windows wake lock. Windows
therefore remains free to sleep whenever there is no active lease or grace period.

## Bounded Tailscale recovery

After three consecutive database probe failures the watcher inspects:

- the `tailscaled` systemd service,
- the `tailscale0` interface,
- `BackendState` from `tailscale status --json`.

Recovery is attempted only when Tailscale itself is unhealthy. A database failure
with a healthy Tailscale snapshot is logged as a database-only problem and does not
restart Tailscale.

The only root actions are fixed argument-list calls through WSL:

```text
systemctl start tailscaled
systemctl restart tailscaled
```

The service name and action set are not user-provided shell commands. The watcher
does not start Docker or PostgreSQL. It never runs `tailscale up`, never logs out,
never uses an auth key and never deletes `tailscaled.state`.

`NeedsLogin`, `NeedsMachineAuth` and `NeedsApproval` remain fail-closed. Recovery
has a 10-minute cooldown and is limited to three attempts per hour.

## Awake-time telemetry

The deployed watcher writes:

```text
%LOCALAPPDATA%\JobPipelineRuntimeLeaseWatcher\origin-runtime-watcher.jsonl
%LOCALAPPDATA%\JobPipelineRuntimeLeaseWatcher\origin-runtime-watcher-state.json
```

The state contains daily and cumulative counters including:

- `total_observed_awake_seconds`,
- `total_lease_active_seconds`,
- `total_awake_without_lease_seconds`,
- `total_suspend_or_unobserved_seconds`,
- Tailscale recovery attempts, successes and failures.

Intervals of at most 30 seconds between watcher observations count as observed
awake time. Larger gaps are recorded as `suspend_or_unobserved` and never counted
as awake time. This is a conservative lower-bound measurement rather than exact
Windows power accounting.

`awake_without_lease` is not automatically a defect because the operator may use
the workstation normally. It helps reveal whether the workstation appears to stay
awake outside actual pipeline runtime leases.

## Installation from the WSL repository

Open a fresh Windows PowerShell window. The following block updates the WSL
repository, copies the installer to a Windows temporary file and installs it:

```powershell
$ErrorActionPreference = "Stop"
$Installer = Join-Path $env:TEMP "install-origin-runtime-watcher.ps1"

$ScriptContent = wsl.exe -d Ubuntu -- bash -lc '
set -e
cd "$HOME/projects/job-application-pipeline"
git checkout main >/dev/null 2>&1
git pull --ff-only origin main >/dev/null 2>&1
cat scripts/install_windows_origin_runtime_lease_watcher.ps1
'

if ($LASTEXITCODE -ne 0 -or -not $ScriptContent) {
    throw "Installer konnte nicht aus dem WSL-Repository gelesen werden."
}

$ScriptContent | Set-Content -LiteralPath $Installer -Encoding UTF8
powershell.exe -NoProfile -ExecutionPolicy Bypass -File $Installer -Install
```

The optional `-ExpectedPipelineSha <40-character SHA>` parameter can pin a specific
reviewed `main` revision during installation.

Re-running `-Install` stops and replaces the existing task, deploys the current
script under `%LOCALAPPDATA%`, runs one foreground probe and then starts the hidden
Scheduled Task.

## Verification

Check task and installation metadata:

```powershell
$Root = Join-Path $env:LOCALAPPDATA "JobPipelineRuntimeLeaseWatcher"

Get-ScheduledTask -TaskName "Job Pipeline Runtime Lease Watcher" |
    Select-Object TaskName, State

Get-Content (Join-Path $Root "installation.json")
Get-Content (Join-Path $Root "origin-runtime-watcher-state.json")
Get-Content (Join-Path $Root "origin-runtime-watcher.jsonl") -Tail 30
Get-Content (Join-Path $Root "watcher.log") -Tail 20
```

Run one foreground observation without changing the registered task:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File "$env:LOCALAPPDATA\JobPipelineRuntimeLeaseWatcher\origin-runtime-lease-watcher.ps1" `
  -Once
```

## Checkpoint and re-wake boundaries

The checkpoint cache remains bound to the exact pipeline commit and projection
fingerprint. Completed companies may be reused only when both values and company
order match exactly.

The private dispatcher remains the remote wake authority. Future local write-back
phases must obtain a new wake and lease rather than extending this read-only
benchmark implicitly.
