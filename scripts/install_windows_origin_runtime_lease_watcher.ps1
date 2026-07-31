param(
    [switch]$Install,
    [switch]$Once,
    [switch]$Uninstall,
    [int]$PollSeconds = 5,
    [int]$GraceSeconds = 90,
    [int]$AwakeGapThresholdSeconds = 30,
    [int]$RecoveryFailures = 3,
    [int]$RecoveryCooldownSeconds = 600,
    [int]$RecoveryMaxPerHour = 3,
    [string]$WslDistro = "Ubuntu",
    [string]$ExpectedPipelineSha = ""
)

$ErrorActionPreference = "Stop"

$TaskName = "Job Pipeline Runtime Lease Watcher"
$DeployRoot = Join-Path $env:LOCALAPPDATA "JobPipelineRuntimeLeaseWatcher"
$InstalledScript = Join-Path $DeployRoot "origin-runtime-lease-watcher.ps1"
$LogPath = Join-Path $DeployRoot "watcher.log"
$TelemetryPath = Join-Path $DeployRoot "origin-runtime-watcher.jsonl"
$StatePath = Join-Path $DeployRoot "origin-runtime-watcher-state.json"
$MetadataPath = Join-Path $DeployRoot "installation.json"
$SchemaVersion = 1
$AuthRequiredStates = @("NeedsLogin", "NeedsMachineAuth", "NeedsApproval")

function Ensure-DeployRoot {
    if (-not (Test-Path $DeployRoot)) {
        New-Item -ItemType Directory -Force -Path $DeployRoot | Out-Null
    }
}

function Write-WatcherLog {
    param([Parameter(Mandatory = $true)][string]$Message)

    Ensure-DeployRoot
    $LogLine = "{0} {1}" -f (Get-Date -Format "o"), $Message
    Add-Content -Path $LogPath -Value $LogLine -Encoding UTF8
    Write-Host $Message
}

function Write-JsonAtomically {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)]$Value
    )

    Ensure-DeployRoot
    $TemporaryPath = "$Path.tmp"
    $Value | ConvertTo-Json -Depth 8 | Set-Content -Path $TemporaryPath -Encoding UTF8
    Move-Item -LiteralPath $TemporaryPath -Destination $Path -Force
}

function Write-TelemetryEvent {
    param(
        [Parameter(Mandatory = $true)][string]$Event,
        [hashtable]$Fields = @{}
    )

    Ensure-DeployRoot
    $Payload = [ordered]@{
        schema_version = $SchemaVersion
        timestamp_utc = (Get-Date).ToUniversalTime().ToString("o")
        event = $Event
    }

    foreach ($Key in $Fields.Keys) {
        $Payload[$Key] = $Fields[$Key]
    }

    Add-Content `
        -Path $TelemetryPath `
        -Value ($Payload | ConvertTo-Json -Compress -Depth 8) `
        -Encoding UTF8
}

function New-WatcherState {
    $Now = (Get-Date).ToUniversalTime()
    return [pscustomobject][ordered]@{
        schema_version = $SchemaVersion
        last_observed_at_utc = $null
        last_lease_active = $false
        watcher_starts = 0
        total_observed_awake_seconds = 0.0
        total_lease_active_seconds = 0.0
        total_awake_without_lease_seconds = 0.0
        total_suspend_or_unobserved_seconds = 0.0
        total_suspend_or_unobserved_events = 0
        total_tailscale_recovery_attempts = 0
        total_tailscale_recovery_successes = 0
        total_tailscale_recovery_failures = 0
        current_day_date = $Now.ToString("yyyy-MM-dd")
        current_day_observed_awake_seconds = 0.0
        current_day_lease_active_seconds = 0.0
        current_day_awake_without_lease_seconds = 0.0
        current_day_suspend_or_unobserved_seconds = 0.0
        current_day_suspend_or_unobserved_events = 0
        current_day_tailscale_recovery_attempts = 0
        current_day_tailscale_recovery_successes = 0
        current_day_tailscale_recovery_failures = 0
    }
}

function Read-WatcherState {
    if (-not (Test-Path $StatePath)) {
        return (New-WatcherState)
    }

    try {
        $State = Get-Content -LiteralPath $StatePath -Raw | ConvertFrom-Json
    }
    catch {
        Write-TelemetryEvent -Event "watcher_state_reset" -Fields @{
            reason = "invalid_json"
        }
        return (New-WatcherState)
    }

    if ($State.schema_version -ne $SchemaVersion) {
        Write-TelemetryEvent -Event "watcher_state_reset" -Fields @{
            reason = "schema_mismatch"
        }
        return (New-WatcherState)
    }

    return $State
}

function Reset-CurrentDay {
    param(
        [Parameter(Mandatory = $true)]$State,
        [Parameter(Mandatory = $true)][datetime]$NowUtc
    )

    $State.current_day_date = $NowUtc.ToString("yyyy-MM-dd")
    $State.current_day_observed_awake_seconds = 0.0
    $State.current_day_lease_active_seconds = 0.0
    $State.current_day_awake_without_lease_seconds = 0.0
    $State.current_day_suspend_or_unobserved_seconds = 0.0
    $State.current_day_suspend_or_unobserved_events = 0
    $State.current_day_tailscale_recovery_attempts = 0
    $State.current_day_tailscale_recovery_successes = 0
    $State.current_day_tailscale_recovery_failures = 0
}

function Roll-CurrentDayIfNeeded {
    param(
        [Parameter(Mandatory = $true)]$State,
        [Parameter(Mandatory = $true)][datetime]$NowUtc
    )

    $CurrentDate = $NowUtc.ToString("yyyy-MM-dd")
    if ($State.current_day_date -eq $CurrentDate) {
        return
    }

    Write-TelemetryEvent -Event "awake_time_daily_summary" -Fields @{
        date = $State.current_day_date
        observed_awake_seconds = $State.current_day_observed_awake_seconds
        lease_active_seconds = $State.current_day_lease_active_seconds
        awake_without_lease_seconds = $State.current_day_awake_without_lease_seconds
        suspend_or_unobserved_seconds = $State.current_day_suspend_or_unobserved_seconds
        suspend_or_unobserved_events = $State.current_day_suspend_or_unobserved_events
        tailscale_recovery_attempts = $State.current_day_tailscale_recovery_attempts
        tailscale_recovery_successes = $State.current_day_tailscale_recovery_successes
        tailscale_recovery_failures = $State.current_day_tailscale_recovery_failures
    }

    Reset-CurrentDay -State $State -NowUtc $NowUtc
}

function Record-Observation {
    param(
        [Parameter(Mandatory = $true)]$State,
        [Parameter(Mandatory = $true)][datetime]$NowUtc,
        [Parameter(Mandatory = $true)][bool]$LeaseActive
    )

    Roll-CurrentDayIfNeeded -State $State -NowUtc $NowUtc

    $PreviousText = $State.last_observed_at_utc
    $PreviousLeaseActive = [bool]$State.last_lease_active
    $State.last_observed_at_utc = $NowUtc.ToString("o")
    $State.last_lease_active = $LeaseActive

    if (-not $PreviousText) {
        return
    }

    try {
        $Previous = [datetime]::Parse($PreviousText).ToUniversalTime()
    }
    catch {
        return
    }

    $DeltaSeconds = ($NowUtc - $Previous).TotalSeconds
    if ($DeltaSeconds -le 0) {
        return
    }

    if ($DeltaSeconds -le $AwakeGapThresholdSeconds) {
        $State.total_observed_awake_seconds += $DeltaSeconds
        $State.current_day_observed_awake_seconds += $DeltaSeconds

        if ($PreviousLeaseActive) {
            $State.total_lease_active_seconds += $DeltaSeconds
            $State.current_day_lease_active_seconds += $DeltaSeconds
        }
        else {
            $State.total_awake_without_lease_seconds += $DeltaSeconds
            $State.current_day_awake_without_lease_seconds += $DeltaSeconds
        }
    }
    else {
        $State.total_suspend_or_unobserved_seconds += $DeltaSeconds
        $State.total_suspend_or_unobserved_events += 1
        $State.current_day_suspend_or_unobserved_seconds += $DeltaSeconds
        $State.current_day_suspend_or_unobserved_events += 1

        Write-TelemetryEvent -Event "suspend_or_unobserved_gap" -Fields @{
            gap_seconds = [math]::Round($DeltaSeconds, 3)
            previous_observed_at_utc = $Previous.ToString("o")
            resumed_observation_at_utc = $NowUtc.ToString("o")
        }
    }
}

function Record-RecoveryResult {
    param(
        [Parameter(Mandatory = $true)]$State,
        [Parameter(Mandatory = $true)][string]$Result
    )

    $State.total_tailscale_recovery_attempts += 1
    $State.current_day_tailscale_recovery_attempts += 1

    if ($Result -eq "completed") {
        $State.total_tailscale_recovery_successes += 1
        $State.current_day_tailscale_recovery_successes += 1
    }
    elseif ($Result -in @("failed", "failed_closed")) {
        $State.total_tailscale_recovery_failures += 1
        $State.current_day_tailscale_recovery_failures += 1
    }
}

function Invoke-WslCommand {
    param([Parameter(Mandatory = $true)][string]$Command)

    $PreviousPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"

    try {
        $Output = @(
            & wsl.exe -d $WslDistro -- bash -lc $Command 2>&1 |
                ForEach-Object { "$_" }
        )
        $ExitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $PreviousPreference
    }

    return [pscustomobject]@{
        Output = $Output
        ExitCode = $ExitCode
    }
}

function Invoke-TailscaledServiceAction {
    param([Parameter(Mandatory = $true)][ValidateSet("start", "restart")][string]$Action)

    $PreviousPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"

    try {
        $Output = @(
            & wsl.exe -d $WslDistro -u root -- systemctl $Action tailscaled 2>&1 |
                ForEach-Object { "$_" }
        )
        $ExitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $PreviousPreference
    }

    return [pscustomobject]@{
        Output = $Output
        ExitCode = $ExitCode
    }
}

function Get-PipelineHead {
    $Command = 'cd "$HOME/projects/job-application-pipeline" && git fetch origin >/dev/null 2>&1 && git checkout main >/dev/null 2>&1 && git pull --ff-only origin main >/dev/null 2>&1 && git rev-parse HEAD'
    $Result = Invoke-WslCommand -Command $Command

    if ($Result.ExitCode -ne 0) {
        throw "Das Pipeline-Repository konnte in WSL nicht aktualisiert werden. Exitcode: $($Result.ExitCode)"
    }

    $Head = (
        $Result.Output |
            Where-Object { $_ -match '^[0-9a-f]{40}$' } |
            Select-Object -Last 1
    )

    if (-not $Head) {
        throw "Der Pipeline-SHA wurde nicht ausgegeben."
    }

    return $Head.Trim()
}

function Get-RuntimeLeaseState {
    $PythonCode = @'
import psycopg
from src.config import get_database_config
from src.search_intelligence.origin_runtime_lease import runtime_lease_present

with psycopg.connect(
    **get_database_config(),
    autocommit=True,
    connect_timeout=3,
) as conn:
    print("active" if runtime_lease_present(conn) else "idle")
'@

    $EncodedPython = [Convert]::ToBase64String(
        [System.Text.Encoding]::UTF8.GetBytes($PythonCode)
    )

    $Command = (
        'cd "$HOME/projects/job-application-pipeline" && ' +
        'printf "%s" "{0}" | base64 -d | .venv/bin/python -'
    ) -f $EncodedPython

    $Result = Invoke-WslCommand -Command $Command

    if ($Result.ExitCode -ne 0) {
        return "unavailable:probe_failed"
    }

    $State = (
        $Result.Output |
            Where-Object { $_ -in @("active", "idle") } |
            Select-Object -Last 1
    )

    if (-not $State) {
        return "unavailable:invalid_output"
    }

    return $State.Trim()
}

function Get-TailscaleSnapshot {
    $Command = @'
service_state="$(systemctl is-active tailscaled 2>/dev/null || true)"
if ip link show tailscale0 >/dev/null 2>&1; then
    interface_state="present"
else
    interface_state="absent"
fi
backend_state="$({ tailscale status --json 2>/dev/null || true; } | python3 -c 'import json,sys
try:
    print(json.load(sys.stdin).get("BackendState", "Unknown"))
except Exception:
    print("Unknown")')"
printf 'service_state=%s\ninterface_state=%s\nbackend_state=%s\n' "$service_state" "$interface_state" "$backend_state"
'@

    $Result = Invoke-WslCommand -Command $Command
    $Values = @{}
    foreach ($Line in $Result.Output) {
        if ($Line -match '^([^=]+)=(.*)$') {
            $Values[$Matches[1]] = $Matches[2]
        }
    }

    return [pscustomobject]@{
        CommandExitCode = $Result.ExitCode
        ServiceState = if ($Values.ContainsKey("service_state")) { $Values["service_state"] } else { "unknown" }
        InterfaceState = if ($Values.ContainsKey("interface_state")) { $Values["interface_state"] } else { "unknown" }
        BackendState = if ($Values.ContainsKey("backend_state")) { $Values["backend_state"] } else { "Unknown" }
    }
}

function Invoke-BoundedTailscaleRecovery {
    $Before = Get-TailscaleSnapshot
    $After = $null
    $Action = "none"
    $Result = "failed"
    $FailureStage = "none"

    if ($Before.BackendState -in $AuthRequiredStates) {
        $Result = "failed_closed"
        $FailureStage = "authentication_required"
    }
    elseif (
        $Before.ServiceState -eq "active" -and
        $Before.InterfaceState -eq "present" -and
        $Before.BackendState -eq "Running"
    ) {
        $Result = "skipped_tailscale_healthy"
        $FailureStage = "database_only"
    }
    else {
        if ($Before.ServiceState -ne "active") {
            $Action = "start"
        }
        else {
            $Action = "restart"
        }

        $ServiceResult = Invoke-TailscaledServiceAction -Action $Action
        if ($ServiceResult.ExitCode -ne 0) {
            $FailureStage = "tailscaled_service_action"
        }
        else {
            Start-Sleep -Seconds 5
            $After = Get-TailscaleSnapshot
            $DatabaseStateAfter = Get-RuntimeLeaseState

            if (
                $After.ServiceState -eq "active" -and
                $After.InterfaceState -eq "present" -and
                $After.BackendState -eq "Running" -and
                $DatabaseStateAfter -in @("active", "idle")
            ) {
                $Result = "completed"
            }
            else {
                $FailureStage = if ($After.BackendState -in $AuthRequiredStates) {
                    "authentication_required_after_action"
                }
                elseif ($After.BackendState -ne "Running") {
                    "tailscale_backend"
                }
                elseif ($After.InterfaceState -ne "present") {
                    "tailscale_interface"
                }
                else {
                    "database_after_tailscale"
                }
            }
        }
    }

    if (-not $After) {
        $After = Get-TailscaleSnapshot
    }

    Write-TelemetryEvent -Event "tailscale_recovery" -Fields @{
        result = $Result
        action = $Action
        failure_stage = $FailureStage
        service_state_before = $Before.ServiceState
        interface_state_before = $Before.InterfaceState
        backend_state_before = $Before.BackendState
        service_state_after = $After.ServiceState
        interface_state_after = $After.InterfaceState
        backend_state_after = $After.BackendState
    }

    Write-WatcherLog (
        "origin_runtime_tailscale_recovery={0} action={1} failure_stage={2}" -f
        $Result,
        $Action,
        $FailureStage
    )

    return $Result
}

if ($Uninstall) {
    $ExistingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue

    if ($ExistingTask) {
        Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    }

    Write-Host "runtime_lease_watcher=uninstalled"
    exit 0
}

if ($Install) {
    Ensure-DeployRoot

    Write-Host "=== 1/5 Pipeline-Stand prüfen ==="
    $PipelineHead = Get-PipelineHead

    if ($ExpectedPipelineSha -and $PipelineHead -ne $ExpectedPipelineSha) {
        throw "Falscher Pipeline-Stand: $PipelineHead; erwartet: $ExpectedPipelineSha"
    }

    Write-Host "pipeline_head=$PipelineHead"

    Write-Host "=== 2/5 Kandidaten-Skript und Rollback vorbereiten ==="
    $CurrentScript = [System.IO.Path]::GetFullPath($PSCommandPath)
    $CandidateScript = Join-Path $DeployRoot "origin-runtime-lease-watcher.candidate.ps1"
    $BackupScript = Join-Path $DeployRoot "origin-runtime-lease-watcher.backup.ps1"
    Copy-Item -LiteralPath $CurrentScript -Destination $CandidateScript -Force

    if (Test-Path $InstalledScript) {
        Copy-Item -LiteralPath $InstalledScript -Destination $BackupScript -Force
    }
    else {
        Remove-Item -LiteralPath $BackupScript -Force -ErrorAction SilentlyContinue
    }

    $ExistingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    $PowerShellExe = Join-Path `
        $env:SystemRoot `
        "System32\WindowsPowerShell\v1.0\powershell.exe"

    Write-Host "=== 3/5 Kandidaten-Skript einmalig prüfen ==="
    if ($ExistingTask -and $ExistingTask.State -eq "Running") {
        Stop-ScheduledTask -TaskName $TaskName -ErrorAction Stop
        Start-Sleep -Seconds 2
    }

    try {
        $OnceOutput = @(
            & $PowerShellExe `
                -NoProfile `
                -ExecutionPolicy Bypass `
                -File $CandidateScript `
                -Once `
                -WslDistro $WslDistro
        )

        if ($LASTEXITCODE -ne 0) {
            $OnceOutput | ForEach-Object { Write-Host $_ }
            throw "Der einmalige Wächter-Test ist fehlgeschlagen."
        }

        $OnceOutput | ForEach-Object { Write-Host $_ }

        $HealthyProbe = (
            $OnceOutput |
                Where-Object {
                    $_ -match '^origin_runtime_lease_watch=(idle|active|unavailable:[^ ]+) wake_lock=false$'
                }
        )

        if (-not $HealthyProbe) {
            throw "Der Wächter lieferte kein gültiges Statussignal."
        }
    }
    catch {
        if ($ExistingTask) {
            Start-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
        }
        throw
    }

    Write-Host "=== 4/5 Task atomar ersetzen ==="
    try {
        if ($ExistingTask) {
            Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        }

        Copy-Item -LiteralPath $CandidateScript -Destination $InstalledScript -Force

        Write-JsonAtomically -Path $MetadataPath -Value ([ordered]@{
            schema_version = $SchemaVersion
            installed_at_utc = (Get-Date).ToUniversalTime().ToString("o")
            pipeline_head = $PipelineHead
            wsl_distro = $WslDistro
            installed_script = $InstalledScript
        })

        $CurrentIdentity = (
            [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
        )

        $ActionArguments = (
            '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "{0}" -WslDistro "{1}"' -f
            $InstalledScript,
            $WslDistro
        )

        $Action = New-ScheduledTaskAction `
            -Execute $PowerShellExe `
            -Argument $ActionArguments

        $Trigger = New-ScheduledTaskTrigger `
            -AtLogOn `
            -User $CurrentIdentity

        $Principal = New-ScheduledTaskPrincipal `
            -UserId $CurrentIdentity `
            -LogonType Interactive `
            -RunLevel Limited

        $Settings = New-ScheduledTaskSettingsSet `
            -AllowStartIfOnBatteries `
            -DontStopIfGoingOnBatteries `
            -StartWhenAvailable `
            -RestartCount 3 `
            -RestartInterval (New-TimeSpan -Minutes 1) `
            -ExecutionTimeLimit (New-TimeSpan -Days 3650)

        $TaskDefinition = New-ScheduledTask `
            -Action $Action `
            -Trigger $Trigger `
            -Principal $Principal `
            -Settings $Settings `
            -Description "Hält Windows nur während einer aktiven Origin-Runtime-Lease wach, protokolliert beobachtete Wachzeit und repariert begrenzt den lokalen Tailscale-Dienst."

        Register-ScheduledTask `
            -TaskName $TaskName `
            -InputObject $TaskDefinition `
            -Force | Out-Null

        Start-ScheduledTask -TaskName $TaskName
        Start-Sleep -Seconds 7

        $Task = Get-ScheduledTask -TaskName $TaskName
        $TaskInfo = Get-ScheduledTaskInfo -TaskName $TaskName

        if ($Task.State -ne "Running") {
            throw "Der Wächter läuft nicht. Status: $($Task.State), Ergebnis: $($TaskInfo.LastTaskResult)"
        }
    }
    catch {
        $InstallationFailure = $_
        $BrokenTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
        if ($BrokenTask) {
            Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
            Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        }

        if (Test-Path $BackupScript) {
            Copy-Item -LiteralPath $BackupScript -Destination $InstalledScript -Force

            $CurrentIdentity = (
                [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
            )
            $RollbackArguments = (
                '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "{0}"' -f
                $InstalledScript
            )
            $RollbackAction = New-ScheduledTaskAction `
                -Execute $PowerShellExe `
                -Argument $RollbackArguments
            $RollbackTrigger = New-ScheduledTaskTrigger `
                -AtLogOn `
                -User $CurrentIdentity
            $RollbackPrincipal = New-ScheduledTaskPrincipal `
                -UserId $CurrentIdentity `
                -LogonType Interactive `
                -RunLevel Limited
            $RollbackSettings = New-ScheduledTaskSettingsSet `
                -AllowStartIfOnBatteries `
                -DontStopIfGoingOnBatteries `
                -StartWhenAvailable `
                -RestartCount 3 `
                -RestartInterval (New-TimeSpan -Minutes 1) `
                -ExecutionTimeLimit (New-TimeSpan -Days 3650)
            $RollbackTask = New-ScheduledTask `
                -Action $RollbackAction `
                -Trigger $RollbackTrigger `
                -Principal $RollbackPrincipal `
                -Settings $RollbackSettings `
                -Description "Rollback des Job Pipeline Runtime Lease Watchers."
            Register-ScheduledTask `
                -TaskName $TaskName `
                -InputObject $RollbackTask `
                -Force | Out-Null
            Start-ScheduledTask -TaskName $TaskName
        }

        throw "Watcher-Installation fehlgeschlagen; vorheriges Skript wurde soweit möglich wiederhergestellt. Ursache: $InstallationFailure"
    }
    finally {
        Remove-Item -LiteralPath $CandidateScript -Force -ErrorAction SilentlyContinue
    }

    Write-Host "=== 5/5 Ergebnis ==="
    Write-Host "pipeline_head=$PipelineHead"
    Write-Host "watcher_task=$($Task.TaskName)"
    Write-Host "watcher_state=$($Task.State)"
    Write-Host "last_task_result=$($TaskInfo.LastTaskResult)"
    Write-Host "watcher_log=$LogPath"
    Write-Host "telemetry_output=$TelemetryPath"
    Write-Host "telemetry_state=$StatePath"
    Write-Host "windows_python_required=false"
    Write-Host "copied_database_env=false"
    Write-Host "runtime_lease_setup=complete"

    exit 0
}

Add-Type @"
using System;
using System.Runtime.InteropServices;

public static class NativePower
{
    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern uint SetThreadExecutionState(uint esFlags);
}
"@

$ES_CONTINUOUS = [Convert]::ToUInt32("80000000", 16)
$ES_SYSTEM_REQUIRED = [uint32]1
$WakeLockActive = $false
$LeaseLastSeen = $null
$ConsecutiveUnavailable = 0
$RecoveryAttemptTimes = @()
$LastRecoveryAttempt = $null
$WatcherState = Read-WatcherState
$WatcherState.watcher_starts += 1
Write-JsonAtomically -Path $StatePath -Value $WatcherState
Write-TelemetryEvent -Event "watcher_started" -Fields @{
    wsl_distro = $WslDistro
    poll_seconds = $PollSeconds
    grace_seconds = $GraceSeconds
    awake_gap_threshold_seconds = $AwakeGapThresholdSeconds
    recovery_failures = $RecoveryFailures
    recovery_cooldown_seconds = $RecoveryCooldownSeconds
    recovery_max_per_hour = $RecoveryMaxPerHour
}

function Set-WindowsAwake {
    param([bool]$Required)

    $Flags = $ES_CONTINUOUS

    if ($Required) {
        $Flags = $Flags -bor $ES_SYSTEM_REQUIRED
    }

    $Result = [NativePower]::SetThreadExecutionState($Flags)

    if ($Result -eq 0) {
        throw "SetThreadExecutionState ist fehlgeschlagen."
    }
}

try {
    while ($true) {
        $State = Get-RuntimeLeaseState
        $Now = Get-Date
        $NowUtc = $Now.ToUniversalTime()
        $LeaseActive = $State -eq "active"

        Record-Observation `
            -State $WatcherState `
            -NowUtc $NowUtc `
            -LeaseActive $LeaseActive

        if ($LeaseActive) {
            $LeaseLastSeen = $Now
        }

        if ($State -like "unavailable:*") {
            $ConsecutiveUnavailable += 1
        }
        else {
            $ConsecutiveUnavailable = 0
        }

        $InsideGrace = $false

        if ($null -ne $LeaseLastSeen) {
            $InsideGrace = (
                ($Now - $LeaseLastSeen).TotalSeconds -le $GraceSeconds
            )
        }

        $ShouldHold = $LeaseActive -or $InsideGrace

        if ($ShouldHold -and -not $WakeLockActive) {
            Set-WindowsAwake -Required $true
            $WakeLockActive = $true
            Write-WatcherLog "origin_runtime_windows_wake_lock=acquired"
        }
        elseif (-not $ShouldHold -and $WakeLockActive) {
            Set-WindowsAwake -Required $false
            $WakeLockActive = $false
            $LeaseLastSeen = $null
            Write-WatcherLog "origin_runtime_windows_wake_lock=released"
        }

        if ($ConsecutiveUnavailable -ge $RecoveryFailures) {
            $Cutoff = $NowUtc.AddHours(-1)
            $RecoveryAttemptTimes = @(
                $RecoveryAttemptTimes | Where-Object { $_ -ge $Cutoff }
            )

            $CooldownSatisfied = (
                $null -eq $LastRecoveryAttempt -or
                ($NowUtc - $LastRecoveryAttempt).TotalSeconds -ge $RecoveryCooldownSeconds
            )
            $RateLimitSatisfied = $RecoveryAttemptTimes.Count -lt $RecoveryMaxPerHour

            if ($CooldownSatisfied -and $RateLimitSatisfied) {
                $LastRecoveryAttempt = $NowUtc
                $RecoveryAttemptTimes += $NowUtc
                $RecoveryResult = Invoke-BoundedTailscaleRecovery
                Record-RecoveryResult -State $WatcherState -Result $RecoveryResult

                if ($RecoveryResult -eq "completed") {
                    $ConsecutiveUnavailable = 0
                }
            }
        }

        Write-JsonAtomically -Path $StatePath -Value $WatcherState

        Write-WatcherLog (
            "origin_runtime_lease_watch={0} wake_lock={1}" -f
            $State,
            $WakeLockActive.ToString().ToLower()
        )

        if ($Once) {
            break
        }

        Start-Sleep -Seconds $PollSeconds
    }
}
finally {
    if ($WakeLockActive) {
        Set-WindowsAwake -Required $false
        Write-WatcherLog "origin_runtime_windows_wake_lock=released_on_exit"
    }

    Write-JsonAtomically -Path $StatePath -Value $WatcherState
    Write-TelemetryEvent -Event "watcher_stopped" -Fields @{
        wake_lock_was_active = $WakeLockActive
    }
}
