param(
    [string]$TaskName = "Job Pipeline Daily Run",
    [string]$DailyTime = "02:30",
    [string]$Distro = "Ubuntu",
    [string]$WslProjectPath = "~/projects/job-application-pipeline",
    [string]$SchedulerDir = "$env:USERPROFILE\job-pipeline-scheduler"
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$SourceScript = Join-Path $RepoRoot "scripts\windows\run_scheduled_pipeline.ps1"
$TargetScript = Join-Path $SchedulerDir "run_scheduled_pipeline.ps1"

New-Item -ItemType Directory -Force $SchedulerDir | Out-Null
Copy-Item -Path $SourceScript -Destination $TargetScript -Force

$Argument = "-NoProfile -ExecutionPolicy Bypass -File `"$TargetScript`" -Distro `"$Distro`" -ProjectPath `"$WslProjectPath`""
$Action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $Argument -WorkingDirectory $SchedulerDir

$DailyTrigger = New-ScheduledTaskTrigger -Daily -At $DailyTime
$LogonTrigger = New-ScheduledTaskTrigger -AtLogOn

$Settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -WakeToRun `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Hours 4)

$Description = "Runs the local job-application-pipeline daily and at logon. The wrapper skips duplicate same-day runs and catches up after missed days."

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger @($DailyTrigger, $LogonTrigger) `
    -Settings $Settings `
    -Description $Description `
    -Force | Out-Null

Write-Host "Installed/updated scheduled task: $TaskName"
Write-Host "Daily trigger: $DailyTime"
Write-Host "Logon catch-up trigger: enabled"
Write-Host "Wrapper script: $TargetScript"
Write-Host "WSL project path: $WslProjectPath"
