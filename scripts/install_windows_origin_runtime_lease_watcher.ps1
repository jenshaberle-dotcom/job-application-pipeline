param(
    [string]$TaskName = "Job Pipeline Runtime Lease Watcher",
    [string]$PythonPath = "",
    [string]$EnvFile = ""
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
if (-not $PythonPath) {
    $PythonPath = Join-Path $RepoRoot ".venv\Scripts\python.exe"
}
if (-not $EnvFile) {
    $EnvFile = Join-Path $RepoRoot ".env"
}

if (-not (Test-Path $PythonPath)) {
    throw "Python interpreter not found: $PythonPath"
}
if (-not (Test-Path $EnvFile)) {
    throw "Environment file not found: $EnvFile"
}

$Arguments = @(
    "-m",
    "scripts.watch_origin_runtime_lease",
    "--env-file",
    ('"{0}"' -f $EnvFile),
    "--poll-seconds",
    "5",
    "--grace-seconds",
    "90"
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
    -Description "Keeps Windows awake only while the GitHub origin runtime owns its PostgreSQL advisory-lock lease." `
    -Force | Out-Null

Start-ScheduledTask -TaskName $TaskName
Write-Host "runtime_lease_watcher_task=installed_and_started"
Write-Host "task_name=$TaskName"
Write-Host "python_path=$PythonPath"
Write-Host "env_file=$EnvFile"
