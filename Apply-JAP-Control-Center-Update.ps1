param(
    [Parameter(Mandatory = $true)]
    [string]$ManifestPath,
    [int]$HostPid = 0,
    [string]$InstallRoot = (Join-Path $env:LOCALAPPDATA "JAP-Control-Center")
)

$ErrorActionPreference = "Stop"
$ExpectedRepositoryId = 1230805345
$ExpectedRepository = "jenshaberle-dotcom/job-application-pipeline"
$ExpectedInstallSchema = "job_application_pipeline.windows_control_center_install.v2"
$ExpectedPendingSchema = "job_application_pipeline.windows_pending_update.v1"
$ExpectedCompatibilityLine = "1"
$ResultSchema = "job_application_pipeline.windows_update_result.v1"
$InstallRoot = [System.IO.Path]::GetFullPath($InstallRoot)
$ManifestPath = [System.IO.Path]::GetFullPath($ManifestPath)
$CurrentPath = Join-Path $InstallRoot "current.json"
$PendingPath = Join-Path $InstallRoot "state\pending-update.json"
$SnoozePath = Join-Path $InstallRoot "state\update-snooze.json"
$ResultPath = Join-Path $InstallRoot "state\update-result.json"
$UpdateLog = Join-Path $InstallRoot "logs\update-apply.log"
$DesktopHostRoot = Join-Path $InstallRoot "desktop-host"
$DesktopHostExe = Join-Path $DesktopHostRoot "JAP.ControlCenter.Desktop.exe"
$UpdatesRoot = [System.IO.Path]::GetFullPath((Join-Path $InstallRoot "updates"))

function Write-JsonAtomic([string]$Path, [object]$Value) {
    $parent = Split-Path -Parent $Path
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    $temporary = "$Path.tmp"
    $Value | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 $temporary
    Move-Item -Force $temporary $Path
}

function Write-UpdateLog([string]$Phase, [string]$Detail = "") {
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $UpdateLog) | Out-Null
    $tab = [char]9
    $line = "{0}{1}{2}{1}{3}" -f [DateTime]::UtcNow.ToString("o"), $tab, $Phase, ($Detail -replace "[\r\n]", " ")
    Add-Content -Encoding UTF8 -Path $UpdateLog -Value $line
}

function Read-Json([string]$Path) {
    if (-not (Test-Path $Path)) {
        throw "Required update metadata is missing: $Path"
    }
    return Get-Content -Raw -Encoding UTF8 $Path | ConvertFrom-Json
}

function Assert-PathUnderUpdates([string]$Path) {
    $fullPath = [System.IO.Path]::GetFullPath($Path)
    $prefix = $UpdatesRoot.TrimEnd([System.IO.Path]::DirectorySeparatorChar) + [System.IO.Path]::DirectorySeparatorChar
    if (-not $fullPath.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Update payload escaped the managed staging root: $fullPath"
    }
    return $fullPath
}

function Invoke-InstalledRunner(
    [object]$Current,
    [string]$PinnedSha,
    [string]$Action
) {
    $linuxRunner = ([string]$Current.wsl_installed_runner_path).Trim()
    if ([string]::IsNullOrWhiteSpace($linuxRunner) -or -not $linuxRunner.StartsWith("/")) {
        throw "Installed JAP WSL runner path is invalid."
    }
    $wsl = Get-Command wsl.exe -ErrorAction SilentlyContinue
    if (-not $wsl) {
        throw "WSL is required to apply JAP Control Center updates."
    }

    $arguments = @(
        "-d",
        [string]$Current.wsl_distro,
        "--exec",
        "bash",
        $linuxRunner,
        [string]$Current.wsl_project_root,
        [string]$Current.managed_worktree,
        $PinnedSha,
        [string]$Current.wsl_state_root,
        $Action
    )
    & $wsl.Source @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Installed JAP runner action '$Action' failed with exit code $LASTEXITCODE."
    }
}

function Restart-JapIfPresent {
    if ($HostPid -le 0) {
        Write-UpdateLog "restart_deferred" "reason=headless_apply_requires_interactive_launch"
        return
    }
    if (Get-Process -Id $HostPid -ErrorAction SilentlyContinue) {
        return
    }
    if (Test-Path $DesktopHostExe) {
        Start-Process -FilePath $DesktopHostExe -WorkingDirectory (Split-Path -Parent $DesktopHostExe) | Out-Null
    }
}

function Remove-AcceptedManifest {
    if ($ManifestPath -ne $PendingPath) {
        Remove-Item -Force $ManifestPath -ErrorAction SilentlyContinue
    }
}

function Move-DirectoryWithRetry(
    [string]$Source,
    [string]$Destination,
    [string]$Phase
) {
    $lastError = $null
    for ($attempt = 1; $attempt -le 40; $attempt++) {
        try {
            Move-Item -Path $Source -Destination $Destination -ErrorAction Stop
            if ($attempt -gt 1) {
                Write-UpdateLog "$($Phase)_retry_pass" "attempt=$attempt"
            }
            return
        }
        catch {
            $lastError = $_.Exception.Message
            if ($attempt -ge 40) { break }
            Start-Sleep -Milliseconds 250
        }
    }
    throw "${Phase} failed after bounded retry: $lastError"
}

$targetVersion = "unknown"
$targetSha = "unknown"
$backupHost = Join-Path $InstallRoot ("desktop-host.previous." + $PID)
$stagedHost = Join-Path $InstallRoot ("desktop-host.staged." + $PID)
$desktopSwapped = $false
$frontendPreparedTarget = $false
$controlPlaneRefreshed = $false
$stableRunnerBackup = Join-Path $InstallRoot ("run-jap-control-center-wsl.previous." + $PID)
$stableApplierBackup = Join-Path $InstallRoot ("Apply-JAP-Control-Center-Update.previous." + $PID + ".ps1")
$previousCurrent = $null

try {
    Write-UpdateLog "update_begin" "manifest=$ManifestPath host_pid=$HostPid"

    $manifest = Read-Json $ManifestPath
    if ($manifest.schema -ne $ExpectedPendingSchema) {
        throw "Unexpected pending update schema: $($manifest.schema)"
    }
    if ($manifest.compatibility_line -ne $ExpectedCompatibilityLine) {
        throw "Unsupported update compatibility line: $($manifest.compatibility_line)"
    }
    if ($manifest.installer_schema -ne $ExpectedInstallSchema) {
        throw "Unsupported installer schema: $($manifest.installer_schema)"
    }

    $targetVersion = [string]$manifest.target_desktop_version
    $targetSha = [string]$manifest.target_main_sha
    $targetRelease = [string]$manifest.target_release_tag
    if ($targetVersion -notmatch '^1\.\d+\.\d+$') {
        throw "Target desktop host is outside direct-upgrade compatibility line 1: $targetVersion"
    }
    if ($targetSha -notmatch '^[0-9a-f]{40}$') {
        throw "Target main SHA is invalid: $targetSha"
    }
    if ($targetRelease -ne "jap-winapp-desktop-v$targetVersion") {
        throw "Target release identity does not match desktop version."
    }

    $previousCurrent = Read-Json $CurrentPath
    $current = Read-Json $CurrentPath
    if ($current.repository_id -ne $ExpectedRepositoryId -or $current.repository -ne $ExpectedRepository) {
        throw "Installed JAP repository identity does not match update authority."
    }
    if ($current.schema -ne $ExpectedInstallSchema) {
        throw "Installed JAP schema is not directly upgradeable: $($current.schema)"
    }
    if ([string]$current.desktop_host_version -notmatch '^1\.\d+\.\d+$') {
        throw "Installed JAP desktop version is outside compatibility line 1: $($current.desktop_host_version)"
    }

    $archive = Assert-PathUnderUpdates ([string]$manifest.desktop_archive)
    $checksum = Assert-PathUnderUpdates ([string]$manifest.desktop_checksum)
    foreach ($required in @($archive, $checksum)) {
        if (-not (Test-Path $required -PathType Leaf)) {
            throw "Staged update payload is incomplete: $required"
        }
    }

    $checksumLine = (Get-Content -Raw $checksum).Trim()
    $expectedHash = ($checksumLine -split '\s+')[0].ToLowerInvariant()
    $manifestHash = ([string]$manifest.desktop_sha256).Trim().ToLowerInvariant()
    $actualHash = (Get-FileHash $archive -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($expectedHash -notmatch '^[0-9a-f]{64}$' -or $expectedHash -ne $actualHash) {
        throw "Staged desktop host checksum verification failed."
    }
    if ($manifestHash -ne $expectedHash) {
        throw "Pending update hash identity does not match the staged checksum."
    }

    if ($HostPid -gt 0) {
        $hostProcess = Get-Process -Id $HostPid -ErrorAction SilentlyContinue
        if ($null -ne $hostProcess) {
            Write-UpdateLog "wait_host_exit" "pid=$HostPid"
            if (-not $hostProcess.WaitForExit(60000)) {
                throw "JAP desktop host did not exit within 60 seconds."
            }
        }
    }

    Write-UpdateLog "runtime_stop"
    Invoke-InstalledRunner $current ([string]$current.pinned_sha) "--stop"
    Remove-Item -Force (Join-Path $InstallRoot "state\runtime.json") -ErrorAction SilentlyContinue

    Write-UpdateLog "frontend_prepare_start" "target=$targetVersion sha=$targetSha"
    Invoke-InstalledRunner $current $targetSha "prepare"
    $frontendPreparedTarget = $true
    Write-UpdateLog "frontend_prepare_pass" "target=$targetVersion sha=$targetSha"

    Remove-Item -Recurse -Force $stagedHost -ErrorAction SilentlyContinue
    Remove-Item -Recurse -Force $backupHost -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Force -Path $stagedHost | Out-Null
    Expand-Archive -Path $archive -DestinationPath $stagedHost -Force
    $stagedExe = Join-Path $stagedHost "JAP.ControlCenter.Desktop.exe"
    $stagedControlPlane = Join-Path $stagedHost "control-plane"
    $stagedApplier = Join-Path $stagedControlPlane "Apply-JAP-Control-Center-Update.ps1"
    $stagedRunner = Join-Path $stagedControlPlane "run-jap-control-center-wsl.sh"
    if (-not (Test-Path $stagedExe -PathType Leaf)) {
        throw "Staged desktop host release is missing JAP.ControlCenter.Desktop.exe."
    }
    foreach ($requiredControlPlane in @($stagedApplier, $stagedRunner)) {
        if (-not (Test-Path $requiredControlPlane -PathType Leaf)) {
            throw "Staged desktop release is missing update control plane: $requiredControlPlane"
        }
    }

    Write-UpdateLog "desktop_cutover_start" "target=$targetVersion sha=$targetSha"
    if (Test-Path $DesktopHostRoot) {
        Move-DirectoryWithRetry $DesktopHostRoot $backupHost "desktop_backup_move"
    }
    try {
        Move-DirectoryWithRetry $stagedHost $DesktopHostRoot "desktop_staged_move"
        $desktopSwapped = $true
    }
    catch {
        if (Test-Path $DesktopHostRoot) {
            Remove-Item -Recurse -Force $DesktopHostRoot -ErrorAction SilentlyContinue
        }
        if (Test-Path $backupHost) {
            Move-DirectoryWithRetry $backupHost $DesktopHostRoot "desktop_inline_rollback_move"
        }
        throw
    }

    $current.pinned_sha = $targetSha
    $current.desktop_host_version = $targetVersion
    $current.desktop_host_sha256 = $actualHash
    $current.desktop_host_release = $targetRelease
    $current.desktop_host_exe = $DesktopHostExe
    $current.installed_at = [DateTime]::UtcNow.ToString("o")
    Write-JsonAtomic $CurrentPath $current

    $deployed = Read-Json $CurrentPath
    if ($deployed.pinned_sha -ne $targetSha) {
        throw "Update verification failed: pinned main is $($deployed.pinned_sha), expected $targetSha."
    }
    if ($deployed.desktop_host_version -ne $targetVersion) {
        throw "Update verification failed: desktop host is $($deployed.desktop_host_version), expected $targetVersion."
    }
    if (-not (Test-Path $DesktopHostExe -PathType Leaf)) {
        throw "Update verification failed: installed desktop host executable is missing."
    }

    $installedControlPlane = Join-Path $DesktopHostRoot "control-plane"
    $nextApplier = Join-Path $installedControlPlane "Apply-JAP-Control-Center-Update.ps1"
    $nextRunner = Join-Path $installedControlPlane "run-jap-control-center-wsl.sh"
    $stableRunnerWindows = Join-Path $InstallRoot "run-jap-control-center-wsl.sh"
    $stableApplierWindows = Join-Path $InstallRoot "Apply-JAP-Control-Center-Update.ps1"
    Copy-Item -Force $stableRunnerWindows $stableRunnerBackup
    Copy-Item -Force $stableApplierWindows $stableApplierBackup
    Copy-Item -Force $nextRunner $stableRunnerWindows
    Copy-Item -Force $nextApplier $stableApplierWindows
    $controlPlaneRefreshed = $true
    Write-UpdateLog "control_plane_refresh_pass" "target=$targetVersion"

    Remove-Item -Force $stableRunnerBackup -ErrorAction SilentlyContinue
    Remove-Item -Force $stableApplierBackup -ErrorAction SilentlyContinue
    Remove-Item -Recurse -Force $backupHost -ErrorAction SilentlyContinue
    $desktopSwapped = $false

    if (Test-Path $PendingPath) {
        try {
            $latestPending = Read-Json $PendingPath
            if ($latestPending.target_main_sha -eq $targetSha -and $latestPending.target_desktop_version -eq $targetVersion) {
                Remove-Item -Force $PendingPath
            }
        }
        catch {
            Write-UpdateLog "pending_cleanup_skipped" $_.Exception.Message
        }
    }
    Remove-Item -Force $SnoozePath -ErrorAction SilentlyContinue
    Remove-AcceptedManifest

    Write-JsonAtomic $ResultPath @{
        schema = $ResultSchema
        status = "success"
        target_main_sha = $targetSha
        target_desktop_version = $targetVersion
        completed_at = [DateTime]::UtcNow.ToString("o")
        detail = ""
    }
    Write-UpdateLog "update_pass" "target=$targetVersion sha=$targetSha"
    Restart-JapIfPresent
    exit 0
}
catch {
    $detail = $_.Exception.Message

    if ((Test-Path $stableRunnerBackup) -or (Test-Path $stableApplierBackup)) {
        try {
            if (Test-Path $stableRunnerBackup) {
                Copy-Item -Force $stableRunnerBackup (Join-Path $InstallRoot "run-jap-control-center-wsl.sh")
            }
            if (Test-Path $stableApplierBackup) {
                Copy-Item -Force $stableApplierBackup (Join-Path $InstallRoot "Apply-JAP-Control-Center-Update.ps1")
            }
            Write-UpdateLog "control_plane_refresh_rollback" "target=$targetVersion"
        }
        catch {
            Write-UpdateLog "control_plane_refresh_rollback_failed" $_.Exception.Message
        }
    }
    Remove-Item -Force $stableRunnerBackup -ErrorAction SilentlyContinue
    Remove-Item -Force $stableApplierBackup -ErrorAction SilentlyContinue

    if ($desktopSwapped -and (Test-Path $backupHost)) {
        try {
            if (Test-Path $DesktopHostRoot) {
                Remove-Item -Recurse -Force $DesktopHostRoot -ErrorAction SilentlyContinue
            }
            Move-Item -Path $backupHost -Destination $DesktopHostRoot
            if ($null -ne $previousCurrent) {
                Write-JsonAtomic $CurrentPath $previousCurrent
            }
            Write-UpdateLog "desktop_cutover_rollback" "target=$targetVersion sha=$targetSha"
        }
        catch {
            Write-UpdateLog "desktop_cutover_rollback_failed" $_.Exception.Message
        }
    }
    if ($frontendPreparedTarget -and $null -ne $previousCurrent) {
        try {
            $previousSha = [string]$previousCurrent.pinned_sha
            if ($previousSha -match '^[0-9a-f]{40}$' -and $previousSha -ne $targetSha) {
                Write-UpdateLog "frontend_rollback_prepare_start" "sha=$previousSha"
                Invoke-InstalledRunner $previousCurrent $previousSha "prepare"
                Write-UpdateLog "frontend_rollback_prepare_pass" "sha=$previousSha"
            }
        }
        catch {
            Write-UpdateLog "frontend_rollback_prepare_failed" $_.Exception.Message
        }
    }
    Remove-Item -Recurse -Force $stagedHost -ErrorAction SilentlyContinue
    Remove-AcceptedManifest

    try {
        Write-JsonAtomic $ResultPath @{
            schema = $ResultSchema
            status = "failed"
            target_main_sha = $targetSha
            target_desktop_version = $targetVersion
            completed_at = [DateTime]::UtcNow.ToString("o")
            detail = $detail
        }
        Write-UpdateLog "update_failed" $detail
    }
    catch {
        # Preserve the original failure even if diagnostics cannot be written.
    }
    Restart-JapIfPresent
    exit 1
}
 -and $previousSha -ne $targetSha) {
                Write-UpdateLog "frontend_rollback_prepare_start" "sha=$previousSha"
                Invoke-InstalledRunner $previousCurrent $previousSha "prepare"
                Write-UpdateLog "frontend_rollback_prepare_pass" "sha=$previousSha"
            }
        }
        catch {
            Write-UpdateLog "frontend_rollback_prepare_failed" $_.Exception.Message
        }
    }
    Remove-Item -Recurse -Force $stagedHost -ErrorAction SilentlyContinue
    Remove-AcceptedManifest
    try {
        Write-JsonAtomic $ResultPath @{
            schema = $ResultSchema
            status = "failed"
            target_main_sha = $targetSha
            target_desktop_version = $targetVersion
            completed_at = [DateTime]::UtcNow.ToString("o")
            detail = $detail
        }
        Write-UpdateLog "update_failed" $detail
    }
    catch {
        # Preserve the original failure even if diagnostics cannot be written.
    }
    Restart-JapIfPresent
    exit 1
}
