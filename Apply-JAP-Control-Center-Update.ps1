param(
    [Parameter(Mandatory = $true)]
    [string]$ManifestPath,
    [Parameter(Mandatory = $true)]
    [int]$HostPid,
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
$CurrentPath = Join-Path $InstallRoot "current.json"
$PendingPath = Join-Path $InstallRoot "state\pending-update.json"
$SnoozePath = Join-Path $InstallRoot "state\update-snooze.json"
$ResultPath = Join-Path $InstallRoot "state\update-result.json"
$UpdateLog = Join-Path $InstallRoot "logs\update-apply.log"
$DesktopHostExe = Join-Path $InstallRoot "desktop-host\JAP.ControlCenter.Desktop.exe"

function Write-JsonAtomic([string]$Path, [object]$Value) {
    $parent = Split-Path -Parent $Path
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    $temporary = "$Path.tmp"
    $Value | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 $temporary
    Move-Item -Force $temporary $Path
}

function Write-UpdateLog([string]$Phase, [string]$Detail = "") {
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $UpdateLog) | Out-Null
    $line = "{0}`t{1}`t{2}" -f [DateTime]::UtcNow.ToString("o"), $Phase, ($Detail -replace "[`r`n]", " ")
    Add-Content -Encoding UTF8 -Path $UpdateLog -Value $line
}

function Read-Json([string]$Path) {
    if (-not (Test-Path $Path)) {
        throw "Required update metadata is missing: $Path"
    }
    return Get-Content -Raw -Encoding UTF8 $Path | ConvertFrom-Json
}

function Restart-JapIfPresent {
    if (Test-Path $DesktopHostExe) {
        Start-Process -FilePath $DesktopHostExe -WorkingDirectory (Split-Path -Parent $DesktopHostExe) | Out-Null
    }
}

$targetVersion = "unknown"
$targetSha = "unknown"
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
    if ($targetVersion -notmatch '^1\.\d+\.\d+$') {
        throw "Target desktop host is outside direct-upgrade compatibility line 1: $targetVersion"
    }
    if ($targetSha -notmatch '^[0-9a-f]{40}$') {
        throw "Target main SHA is invalid: $targetSha"
    }

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

    $sourceRoot = [System.IO.Path]::GetFullPath([string]$manifest.source_root)
    $archive = [System.IO.Path]::GetFullPath([string]$manifest.desktop_archive)
    $checksum = [System.IO.Path]::GetFullPath([string]$manifest.desktop_checksum)
    $installer = Join-Path $sourceRoot "install-jap-control-center.ps1"
    foreach ($required in @($sourceRoot, $archive, $checksum, $installer)) {
        if (-not (Test-Path $required)) {
            throw "Staged update payload is incomplete: $required"
        }
    }

    $checksumLine = (Get-Content -Raw $checksum).Trim()
    $expectedHash = ($checksumLine -split '\s+')[0].ToLowerInvariant()
    $actualHash = (Get-FileHash $archive -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($expectedHash -notmatch '^[0-9a-f]{64}$' -or $expectedHash -ne $actualHash) {
        throw "Staged desktop host checksum verification failed."
    }

    $host = Get-Process -Id $HostPid -ErrorAction SilentlyContinue
    if ($null -ne $host) {
        Write-UpdateLog "wait_host_exit" "pid=$HostPid"
        if (-not $host.WaitForExit(60000)) {
            throw "JAP desktop host did not exit within 60 seconds."
        }
    }

    $stopper = Join-Path $InstallRoot "Stop-JAP-Control-Center.ps1"
    if (Test-Path $stopper) {
        Write-UpdateLog "runtime_stop"
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $stopper | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw "Managed JAP runtime stop failed with exit code $LASTEXITCODE."
        }
    }

    Write-UpdateLog "installer_start" "target=$targetVersion sha=$targetSha"
    & powershell.exe `
        -NoProfile `
        -ExecutionPolicy Bypass `
        -File $installer `
        -InstallRoot $InstallRoot `
        -WslDistro ([string]$current.wsl_distro) `
        -WslProjectRoot ([string]$current.wsl_project_root) `
        -WslInstalledRunnerPath ([string]$current.wsl_installed_runner_path) `
        -PinnedSha $targetSha `
        -DesktopHostArchivePath $archive `
        -DesktopHostChecksumPath $checksum `
        -NoStart
    if ($LASTEXITCODE -ne 0) {
        throw "JAP installer failed with exit code $LASTEXITCODE."
    }

    $deployed = Read-Json $CurrentPath
    if ($deployed.pinned_sha -ne $targetSha) {
        throw "Update verification failed: pinned main is $($deployed.pinned_sha), expected $targetSha."
    }
    if ($deployed.desktop_host_version -ne $targetVersion) {
        throw "Update verification failed: desktop host is $($deployed.desktop_host_version), expected $targetVersion."
    }

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
