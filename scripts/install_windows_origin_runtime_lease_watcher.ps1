param(
    [string]$TaskName = "Job Pipeline Runtime Lease Watcher",
    [string]$PythonPath = "",
    [string]$EnvFile = "",
    [string]$WslDistro = "Ubuntu",
    [string]$TelemetryOutput = "",
    [string]$TelemetryState = ""
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
if (-not $PythonPath) {
    $PythonPath = Join-Path $RepoRoot ".venv\Scripts\python.exe"
}
if (-not $EnvFile) {
    $EnvFile = Join-Path $RepoRoot ".env"
}
if (-not $TelemetryOutput) {
    $TelemetryOutput = Join-Path $RepoRoot ".runtime\origin-runtime-watcher.jsonl"
}
if (-not $TelemetryState) {
    $TelemetryState = Join-Path $RepoRoot ".runtime\origin-runtime-watcher-state.json"
}

if (-not (Test-Path $PythonPath)) {
    throw "Python interpreter not found: $PythonPath"
}
if (-not (Test-Path $EnvFile)) {
    throw "Environment file not found: $EnvFile"
}

$RuntimeDirectory = Split-Path -Parent $TelemetryOutput
New-Item -ItemType Directory -Path $RuntimeDirectory -Force | Out-Null

$Arguments = @(
    "-m",
    "scripts.watch_origin_runtime_lease",
    "--env-file",
    ('"{0}"' -f $EnvFile),
    "--poll-seconds",
    "5",
    "--grace-seconds",
    "90",
    "--telemetry-output",
    ('"{0}"' -f $TelemetryOutput),
    "--telemetry-state",
    ('"{0}"' -f $TelemetryState),
    "--wsl-distro",
    ('"{0}"' -f $WslDistro),
    "--awake-gap-threshold-seconds",
    "30",
    "--recovery-failures",
    "3",
    "--recovery-cooldown-seconds",
    "600",
    "--recovery-max-per-hour",
    "3"
) -join " "

$Action = New-ScheduledTaskAction `
    -Execute $PythonPath `
    -Argument $Arguments `
    -WorkingDirectory $RepoRoot

$Trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit (New-TimeSpan -Days 3650)

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description "Holds the Windows wake lock only for an active origin-runtime lease, records awake telemetry and performs bounded local Tailscale recovery." `
    -Force | Out-Null

Start-ScheduledTask -TaskName $TaskName
Write-Host "runtime_lease_watcher_task=installed_and_started"
Write-Host "task_name=$TaskName"
Write-Host "python_path=$PythonPath"
Write-Host "env_file=$EnvFile"
Write-Host "wsl_distro=$WslDistro"
Write-Host "telemetry_output=$TelemetryOutput"
Write-Host "telemetry_state=$TelemetryState"
