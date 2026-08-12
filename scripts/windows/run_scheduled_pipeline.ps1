param(
    [string]$Distro = "Ubuntu",
    [switch]$Force
)

$ErrorActionPreference = "Continue"

$RepositoryId = 1230805345
$Repository = "jenshaberle-dotcom/job-application-pipeline"
$RunnerName = "job-pipeline-runtime-linux"
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
        wrapper_version = "rcc-runtime-context-v1"
    }

    $State | ConvertTo-Json | Set-Content -Path $StateFile -Encoding UTF8
}

Log "START scheduled job pipeline wrapper"
Log "User: $env:USERNAME"
Log "Computer: $env:COMPUTERNAME"
Log "Distro: $Distro"
Log "RCC repository ID: $RepositoryId"
Log "RCC runner: $RunnerName"
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
# used as readiness authority; RCC and the Pipeline probe the configured Postgres
# connection directly.
$DockerDesktop = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
if (Test-Path $DockerDesktop) {
    Log "Starting Docker Desktop if needed"
    Start-Process $DockerDesktop
}
else {
    Log "INFO Docker Desktop executable not present; configured DB may be external"
}

Log "Resolving RCC-owned WSL runtime context"
$WslHomeOutput = & wsl -d $Distro -- sh -lc 'printf "%s" "$HOME"' 2>&1
$WslHomeExitCode = $LASTEXITCODE
if ($WslHomeExitCode -ne 0) {
    Add-Content -Path $LogFile -Value $WslHomeOutput
    Log "FAILED WSL home resolution exit_code=$WslHomeExitCode"
    exit $WslHomeExitCode
}
$WslHome = ($WslHomeOutput | Out-String).Trim()
if (-not $WslHome.StartsWith("/")) {
    Log "FAILED invalid WSL home returned by runtime"
    exit 1
}

$ContextPath = "$WslHome/.config/DeepOceanInfrastructure/RCC/runtime-contexts/$RepositoryId-$RunnerName.json"
$ContextOutput = & wsl -d $Distro -- cat $ContextPath 2>&1
$ContextExitCode = $LASTEXITCODE
if ($ContextExitCode -ne 0) {
    Add-Content -Path $LogFile -Value $ContextOutput
    Log "FAILED RCC runtime context unavailable: RUNTIME_CONTEXT_NOT_REGISTERED"
    exit $ContextExitCode
}

try {
    $Context = (($ContextOutput -join "`n") | ConvertFrom-Json)
}
catch {
    Log "FAILED RCC runtime context projection parse: $($_.Exception.Message)"
    exit 1
}

if ([int64]$Context.RepositoryId -ne $RepositoryId -or $Context.Repository -ne $Repository) {
    Log "FAILED RCC runtime context repository identity mismatch"
    exit 1
}
if ($Context.RunnerName -ne $RunnerName -or $Context.Platform -ne "linux-wsl") {
    Log "FAILED RCC runtime context runner/platform mismatch"
    exit 1
}
if ($Context.Status -ne "PASS" -or -not [string]::IsNullOrEmpty([string]$Context.PrimaryFailure)) {
    Log "FAILED RCC runtime context is not PASS status=$($Context.Status) failure=$($Context.PrimaryFailure)"
    exit 1
}
if ($Context.ProjectionPath -and $Context.ProjectionPath -ne $ContextPath) {
    Log "FAILED RCC runtime context projection path mismatch"
    exit 1
}

$RequiredChecks = @(
    "repository_identity",
    "checkout",
    "checkout_repository",
    "env_file",
    "env_keys",
    "interpreter",
    "interpreter_probe",
    "capability:postgresql"
)
foreach ($CheckId in $RequiredChecks) {
    $Matches = @($Context.Checks | Where-Object { $_.Id -eq $CheckId -and $_.Status -eq "PASS" })
    if ($Matches.Count -ne 1) {
        Log "FAILED RCC runtime context required check not PASS: $CheckId"
        exit 1
    }
}

$ProjectPath = [string]$Context.CheckoutRoot
$RuntimePython = [string]$Context.Interpreter
if (-not $ProjectPath.StartsWith("/") -or -not $RuntimePython.StartsWith("$ProjectPath/")) {
    Log "FAILED RCC runtime context returned invalid checkout/interpreter binding"
    exit 1
}

Log "RCC context: $ContextPath"
Log "ProjectPath: $ProjectPath"
Log "RuntimePython: $RuntimePython"
Log "RCC validated at: $($Context.ValidatedAt)"

& wsl -d $Distro -- test -d $ProjectPath
if ($LASTEXITCODE -ne 0) {
    Log "FAILED RCC checkout no longer exists"
    exit 1
}
& wsl -d $Distro -- test -x $RuntimePython
if ($LASTEXITCODE -ne 0) {
    Log "FAILED RCC interpreter no longer exists or is not executable"
    exit 1
}

Log "Verifying and fast-forwarding RCC-resolved Pipeline checkout"
$PreflightOutput = & wsl -d $Distro --cd $ProjectPath -- $RuntimePython -m scripts.prepare_scheduled_pipeline_checkout --root . 2>&1
$PreflightExitCode = $LASTEXITCODE
Add-Content -Path $LogFile -Value $PreflightOutput
Log "checkout_preflight_exit_code=$PreflightExitCode"

if ($PreflightExitCode -ne 0) {
    Log "FAILED scheduled checkout preflight; refusing to run stale/diverged/unverified Pipeline"
    exit $PreflightExitCode
}

Log "Running WSL daily pipeline script from RCC-resolved checkout"
$PipelineOutput = & wsl -d $Distro --cd $ProjectPath -- ./scripts/run_daily_pipeline.sh 2>&1
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
