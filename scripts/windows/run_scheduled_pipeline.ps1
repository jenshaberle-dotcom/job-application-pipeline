param(
    [string]$Distro = "Ubuntu",
    [string]$ProjectPath = "~/projects/job-application-pipeline",
    [switch]$Force
)

$ErrorActionPreference = "Continue"

$SchedulerDir = Join-Path $env:USERPROFILE "job-pipeline-scheduler"
$LogDir = Join-Path $env:USERPROFILE "job-pipeline-scheduler-logs"
$StateDir = Join-Path $SchedulerDir "state"
$StateFile = Join-Path $StateDir "daily-pipeline-state.json"

New-Item -ItemType Directory -Force $SchedulerDir | Out-Null
New-Item -ItemType Directory -Force $LogDir | Out-Null
New-Item -ItemType Directory -Force $StateDir | Out-Null

$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$LogFile = Join-Path $LogDir "scheduled-pipeline_$Timestamp.log"

function Log($Message) {
    $Line = "$(Get-Date -Format "yyyy-MM-dd HH:mm:ss") | $Message"
    Add-Content -Path $LogFile -Value $Line
}

function Read-State() {
    if (-not (Test-Path $StateFile)) {
        return $null
    }

    try {
        return Get-Content -Path $StateFile -Raw | ConvertFrom-Json
    }
    catch {
        Log "WARN failed to parse state file: $($_.Exception.Message)"
        return $null
    }
}

function Write-Success-State($PipelineExitCode) {
    $Now = Get-Date
    $State = [ordered]@{
        last_successful_local_date = $Now.ToString("yyyy-MM-dd")
        last_successful_timestamp_local = $Now.ToString("o")
        last_successful_log_file = $LogFile
        last_pipeline_exit_code = $PipelineExitCode
        wrapper_version = "s2p-origin-freshness-v2"
    }

    $State | ConvertTo-Json | Set-Content -Path $StateFile -Encoding UTF8
}

Log "START scheduled job pipeline wrapper"
Log "User: $env:USERNAME"
Log "Computer: $env:COMPUTERNAME"
Log "Distro: $Distro"
Log "ProjectPath: $ProjectPath"
Log "Force: $Force"

$Today = (Get-Date).ToString("yyyy-MM-dd")
$State = Read-State

if (-not $Force -and $State -and $State.last_successful_local_date -eq $Today) {
    Log "SKIP daily pipeline already completed successfully for local date $Today"
    Log "Previous success log: $($State.last_successful_log_file)"
    Log "END scheduled job pipeline wrapper SKIPPED_ALREADY_DONE_TODAY"
    exit 0
}

# Docker Desktop may host the configured local database, so starting it remains a
# harmless availability aid. Docker CLI presence inside WSL is deliberately NOT
# used as readiness authority; the Pipeline itself probes its configured Postgres
# connection directly with psycopg.
$DockerDesktop = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
if (Test-Path $DockerDesktop) {
    Log "Starting Docker Desktop if needed"
    Start-Process $DockerDesktop
}
else {
    Log "INFO Docker Desktop executable not present; configured DB may be external"
}

Log "Verifying and fast-forwarding persistent Pipeline checkout"
$PreflightCommand = "cd $ProjectPath && .venv/bin/python scripts/prepare_scheduled_pipeline_checkout.py --root ."
$PreflightOutput = & wsl -d $Distro -- bash -lc $PreflightCommand 2>&1
$PreflightExitCode = $LASTEXITCODE
Add-Content -Path $LogFile -Value $PreflightOutput
Log "checkout_preflight_exit_code=$PreflightExitCode"

if ($PreflightExitCode -ne 0) {
    Log "FAILED scheduled checkout preflight; refusing to run stale/diverged/unverified Pipeline"
    exit $PreflightExitCode
}

Log "Running WSL daily pipeline script"
$PipelineCommand = "cd $ProjectPath && ./scripts/run_daily_pipeline.sh"
$PipelineOutput = & wsl -d $Distro -- bash -lc $PipelineCommand 2>&1
$PipelineExitCode = $LASTEXITCODE

Add-Content -Path $LogFile -Value $PipelineOutput
Log "pipeline_exit_code=$PipelineExitCode"

if ($PipelineExitCode -ne 0) {
    Log "FAILED scheduled job pipeline"
    exit $PipelineExitCode
}

Write-Success-State -PipelineExitCode $PipelineExitCode

Log "END scheduled job pipeline wrapper OK"
exit 0
