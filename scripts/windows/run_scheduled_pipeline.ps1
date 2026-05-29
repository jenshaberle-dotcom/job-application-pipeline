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
        wrapper_version = "s2p-catchup-watchdog"
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

$DockerDesktop = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
if (Test-Path $DockerDesktop) {
    Log "Starting Docker Desktop"
    Start-Process $DockerDesktop
}
else {
    Log "WARN Docker Desktop executable not found at $DockerDesktop"
}

$MaxAttempts = 30
$SleepSeconds = 10
$Ready = $false

for ($i = 1; $i -le $MaxAttempts; $i++) {
    Log "Docker/Postgres readiness attempt $i/$MaxAttempts"

    $Command = 'docker ps && docker exec -i job_pipeline_postgres pg_isready -U job_user -d job_pipeline'
    $Output = & wsl -d $Distro -- bash -lc $Command 2>&1
    $ExitCode = $LASTEXITCODE

    Add-Content -Path $LogFile -Value $Output
    Log "readiness_exit_code=$ExitCode"

    if ($ExitCode -eq 0 -and ($Output -join "`n") -match "accepting connections") {
        Log "SUCCESS Docker/Postgres ready"
        $Ready = $true
        break
    }

    Start-Sleep -Seconds $SleepSeconds
}

if (-not $Ready) {
    Log "FAILED Docker/Postgres not ready after retries"
    exit 1
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
