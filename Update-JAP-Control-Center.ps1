param(
    [string]$InstallRoot = (Join-Path $env:LOCALAPPDATA "JAP-Control-Center")
)

$ErrorActionPreference = "Stop"
$ExpectedRepositoryId = 1230805345
$ExpectedOrigin = "jenshaberle-dotcom/job-application-pipeline"
$ExpectedUpdateMode = "gui_prompt_latest_direct_v1"
$InstallRoot = [System.IO.Path]::GetFullPath($InstallRoot)
$CurrentPath = Join-Path $InstallRoot "current.json"
$PendingPath = Join-Path $InstallRoot "state\pending-update.json"
$SnoozePath = Join-Path $InstallRoot "state\update-snooze.json"
$DesktopHostExe = Join-Path $InstallRoot "desktop-host\JAP.ControlCenter.Desktop.exe"

function Read-Json([string]$Path) {
    if (-not (Test-Path $Path)) { return $null }
    return Get-Content -Raw -Encoding UTF8 $Path | ConvertFrom-Json
}

$current = Read-Json $CurrentPath
if (-not $current) {
    throw "JAP Control Center is not installed."
}
if ([int64]$current.repository_id -ne $ExpectedRepositoryId) {
    throw "JAP Control Center repository identity mismatch."
}
if ([string]$current.repository -ne $ExpectedOrigin) {
    throw "JAP Control Center repository name mismatch."
}
if ([string]$current.update_mode -ne $ExpectedUpdateMode) {
    throw "This installation has not yet adopted GUI-managed updates. Wait for the local runner bootstrap."
}

$pending = Read-Json $PendingPath
if (-not $pending) {
    Write-Host "JAP_CONTROL_CENTER_UPDATE=NO_STAGED_UPDATE"
    Write-Host "UPDATE_MODE=$ExpectedUpdateMode"
    Write-Host "Updates are staged by the local JAP runner and offered inside the application."
    exit 0
}

Remove-Item -Force $SnoozePath -ErrorAction SilentlyContinue
Write-Host "JAP_CONTROL_CENTER_UPDATE=PROMPT_REQUESTED"
Write-Host "TARGET_MAIN=$($pending.target_main_sha)"
Write-Host "TARGET_DESKTOP_VERSION=$($pending.target_desktop_version)"
Write-Host "The six-hour snooze was cleared. The running application will offer the staged update on its next poll."

if (-not (Get-Process -Name "JAP.ControlCenter.Desktop" -ErrorAction SilentlyContinue) -and (Test-Path $DesktopHostExe)) {
    Start-Process -FilePath $DesktopHostExe -WorkingDirectory (Split-Path -Parent $DesktopHostExe) | Out-Null
    Write-Host "JAP_CONTROL_CENTER_DESKTOP=STARTED"
}
