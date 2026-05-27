$ErrorActionPreference = "Continue"

$LogDir = Join-Path $env:USERPROFILE "job-pipeline-scheduler-logs"
New-Item -ItemType Directory -Force $LogDir | Out-Null

$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$LogFile = Join-Path $LogDir "scheduled-pipeline_$Timestamp.log"

function Log($Message) {
    $Line = "$(Get-Date -Format "yyyy-MM-dd HH:mm:ss") | $Message"
    Add-Content -Path $LogFile -Value $Line
}

Log "START scheduled job pipeline wrapper"
Log "User: $env:USERNAME"
Log "Computer: $env:COMPUTERNAME"

Log "Starting Docker Desktop"
Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe"

$MaxAttempts = 30
$SleepSeconds = 10
$Ready = $false

for ($i = 1; $i -le $MaxAttempts; $i++) {
    Log "Docker/Postgres readiness attempt $i/$MaxAttempts"

    $Command = 'docker ps && docker exec -i job_pipeline_postgres pg_isready -U job_user -d job_pipeline'
    $Output = & wsl -d Ubuntu -- bash -lc $Command 2>&1
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

$PipelineCommand = 'cd ~/projects/job-application-pipeline && ./scripts/run_daily_pipeline.sh'
$PipelineOutput = & wsl -d Ubuntu -- bash -lc $PipelineCommand 2>&1
$PipelineExitCode = $LASTEXITCODE

Add-Content -Path $LogFile -Value $PipelineOutput
Log "pipeline_exit_code=$PipelineExitCode"

if ($PipelineExitCode -ne 0) {
    Log "FAILED scheduled job pipeline"
    exit $PipelineExitCode
}

Log "END scheduled job pipeline wrapper OK"
exit 0
