param(
    [string]$InstallRoot = (Join-Path $env:LOCALAPPDATA "JAP-Control-Center"),
    [string]$WslDistro,
    [string]$WslProjectRoot,
    [string]$WslInstalledRunnerPath,
    [string]$PinnedSha,
    [string]$DesktopHostArchivePath,
    [string]$DesktopHostChecksumPath,
    [switch]$NoStart,
    [switch]$NoShortcuts
)

$ErrorActionPreference = "Stop"
$ExpectedRepositoryId = 1230805345
$ExpectedOrigin = "jenshaberle-dotcom/job-application-pipeline"
$ReadOnlyFetchUrl = "https://github.com/$ExpectedOrigin.git"
$DesktopHostAsset = "JAP-Control-Center-Desktop-win-x64.zip"
$InstallSchema = "job_application_pipeline.windows_control_center_install.v2"
$UpdateMode = "gui_prompt_latest_direct_v1"
$CompatibilityLine = "1"
$Port = 8780
$InstallRoot = [System.IO.Path]::GetFullPath($InstallRoot)
$CurrentPath = Join-Path $InstallRoot "current.json"
$StableLauncher = Join-Path $InstallRoot "JAP-Control-Center.ps1"
$LegacyStableUpdater = Join-Path $InstallRoot "Update-JAP-Control-Center.ps1"
$StableStopper = Join-Path $InstallRoot "Stop-JAP-Control-Center.ps1"
$StableApplier = Join-Path $InstallRoot "Apply-JAP-Control-Center-Update.ps1"
$StableRunner = Join-Path $InstallRoot "run-jap-control-center-wsl.sh"
$DesktopHostRoot = Join-Path $InstallRoot "desktop-host"
$DesktopHostExe = Join-Path $DesktopHostRoot "JAP.ControlCenter.Desktop.exe"

function Write-JsonAtomic([string]$Path, [object]$Value) {
    $parent = Split-Path -Parent $Path
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    $temporary = "$Path.tmp"
    $Value | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 $temporary
    Move-Item -Force $temporary $Path
}

function Invoke-Wsl([string[]]$Arguments) {
    $output = & wsl.exe @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "WSL command failed: wsl.exe $($Arguments -join ' ')"
    }
    return $output
}

function Test-WslPath([string]$Distro, [string]$Path) {
    & wsl.exe -d $Distro --exec test -e $Path
    return $LASTEXITCODE -eq 0
}

function New-AppShortcut(
    [string]$Path,
    [string]$Target,
    [string]$Arguments,
    [string]$IconLocation = ""
) {
    $parent = Split-Path -Parent $Path
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($Path)
    $shortcut.TargetPath = $Target
    $shortcut.Arguments = $Arguments
    $shortcut.WorkingDirectory = $InstallRoot
    if ([string]::IsNullOrWhiteSpace($IconLocation)) {
        $shortcut.IconLocation = "$env:SystemRoot\System32\imageres.dll,15"
    }
    else {
        $shortcut.IconLocation = $IconLocation
    }
    $shortcut.Save()
}

function Install-DesktopHost(
    [string]$Version,
    [string]$ArchivePath,
    [string]$ChecksumPath,
    [string]$SourceSha
) {
    if ($Version -notmatch '^\d+\.\d+\.\d+$') {
        throw "Invalid JAP desktop host version: $Version"
    }
    if ($SourceSha -notmatch '^[0-9a-f]{40}$') {
        throw "Invalid JAP desktop host source SHA: $SourceSha"
    }

    $tag = "jap-winapp-desktop-v$Version"
    $releaseBase = "https://github.com/$ExpectedOrigin/releases/download/$tag"
    $tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("jap-desktop-host-" + [guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Force -Path $tempRoot | Out-Null

    $useLocalPayload = -not [string]::IsNullOrWhiteSpace($ArchivePath) -or -not [string]::IsNullOrWhiteSpace($ChecksumPath)
    if ($useLocalPayload) {
        if ([string]::IsNullOrWhiteSpace($ArchivePath) -or [string]::IsNullOrWhiteSpace($ChecksumPath)) {
            throw "Desktop host archive and checksum must be supplied together."
        }
        $zip = [System.IO.Path]::GetFullPath($ArchivePath)
        $checksum = [System.IO.Path]::GetFullPath($ChecksumPath)
        if (-not (Test-Path $zip) -or -not (Test-Path $checksum)) {
            throw "Staged desktop host payload is incomplete."
        }
    }
    else {
        $zip = Join-Path $tempRoot $DesktopHostAsset
        $checksum = "$zip.sha256"
        Invoke-WebRequest -UseBasicParsing -Uri "$releaseBase/$DesktopHostAsset" -OutFile $zip
        Invoke-WebRequest -UseBasicParsing -Uri "$releaseBase/$DesktopHostAsset.sha256" -OutFile $checksum
    }

    $staged = Join-Path $InstallRoot ("desktop-host.staged." + $PID)
    $backup = Join-Path $InstallRoot ("desktop-host.previous." + $PID)
    try {
        $checksumLine = (Get-Content -Raw $checksum).Trim()
        $expectedHash = ($checksumLine -split '\s+')[0].ToLowerInvariant()
        if ($expectedHash -notmatch '^[0-9a-f]{64}$') {
            throw "Desktop host release checksum is invalid."
        }
        $actualHash = (Get-FileHash $zip -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actualHash -ne $expectedHash) {
            throw "Desktop host release checksum mismatch."
        }

        Remove-Item -Recurse -Force $staged -ErrorAction SilentlyContinue
        New-Item -ItemType Directory -Force -Path $staged | Out-Null
        Expand-Archive -Path $zip -DestinationPath $staged -Force
        $stagedExe = Join-Path $staged "JAP.ControlCenter.Desktop.exe"
        if (-not (Test-Path $stagedExe)) {
            throw "Desktop host release is missing JAP.ControlCenter.Desktop.exe."
        }

        $stagedFrontend = Join-Path $staged "frontend-dist"
        $stagedFrontendIndex = Join-Path $stagedFrontend "index.html"
        $stagedFrontendMarker = Join-Path $stagedFrontend ".jap-source-sha"
        if (-not (Test-Path $stagedFrontendIndex) -or -not (Test-Path $stagedFrontendMarker)) {
            throw "Desktop host release is missing the source-bound prebuilt frontend."
        }
        $frontendSourceSha = (Get-Content -Raw $stagedFrontendMarker).Trim().ToLowerInvariant()
        if ($frontendSourceSha -ne $SourceSha.ToLowerInvariant()) {
            throw "Desktop host prebuilt frontend source mismatch: $frontendSourceSha expected $SourceSha"
        }

        Remove-Item -Recurse -Force $backup -ErrorAction SilentlyContinue
        if (Test-Path $DesktopHostRoot) {
            Move-Item -Path $DesktopHostRoot -Destination $backup
        }
        try {
            Move-Item -Path $staged -Destination $DesktopHostRoot
        }
        catch {
            if (Test-Path $DesktopHostRoot) {
                Remove-Item -Recurse -Force $DesktopHostRoot -ErrorAction SilentlyContinue
            }
            if (Test-Path $backup) {
                Move-Item -Path $backup -Destination $DesktopHostRoot
            }
            throw
        }
        Remove-Item -Recurse -Force $backup -ErrorAction SilentlyContinue

        return @{
            version = $Version
            sha256 = $actualHash
            tag = $tag
            frontend_source_sha = $frontendSourceSha
        }
    }
    finally {
        Remove-Item -Recurse -Force $staged -ErrorAction SilentlyContinue
        Remove-Item -Recurse -Force $tempRoot -ErrorAction SilentlyContinue
    }
}

function Prepare-ManagedWorktree(
    [string]$Distro,
    [string]$ProjectRoot,
    [string]$ManagedWorktree,
    [string]$WslHome,
    [string]$SourceSha
) {
    $managedGit = "$ManagedWorktree/.git"
    if (Test-WslPath $Distro $managedGit) {
        $statusOutput = Invoke-Wsl @("-d", $Distro, "--exec", "git", "-C", $ManagedWorktree, "status", "--porcelain")
        $status = (($statusOutput -join "`n") -as [string]).Trim()
        if (-not [string]::IsNullOrWhiteSpace($status)) {
            throw "Managed JAP worktree is dirty; refusing update-time source preparation."
        }
        $currentOutput = Invoke-Wsl @("-d", $Distro, "--exec", "git", "-C", $ManagedWorktree, "rev-parse", "HEAD")
        $currentSha = (($currentOutput | Select-Object -First 1) -as [string]).Trim().ToLowerInvariant()
        if ($currentSha -ne $SourceSha.ToLowerInvariant()) {
            Invoke-Wsl @("-d", $Distro, "--exec", "git", "-C", $ManagedWorktree, "checkout", "--detach", $SourceSha) | Out-Null
        }
    }
    else {
        $managedParent = "$WslHome/.local/share/jap-control-center"
        Invoke-Wsl @("-d", $Distro, "--exec", "mkdir", "-p", $managedParent) | Out-Null
        Invoke-Wsl @("-d", $Distro, "--exec", "git", "-C", $ProjectRoot, "worktree", "prune") | Out-Null
        Invoke-Wsl @("-d", $Distro, "--exec", "git", "-C", $ProjectRoot, "worktree", "add", "--detach", $ManagedWorktree, $SourceSha) | Out-Null
    }

    $verifiedOutput = Invoke-Wsl @("-d", $Distro, "--exec", "git", "-C", $ManagedWorktree, "rev-parse", "HEAD")
    $verifiedSha = (($verifiedOutput | Select-Object -First 1) -as [string]).Trim().ToLowerInvariant()
    if ($verifiedSha -ne $SourceSha.ToLowerInvariant()) {
        throw "Managed JAP worktree source mismatch after preparation: $verifiedSha expected $SourceSha"
    }
}

function Install-SourceBoundFrontend(
    [string]$Distro,
    [string]$ManagedWorktree,
    [string]$SourceSha
) {
    $windowsFrontend = Join-Path $DesktopHostRoot "frontend-dist"
    $windowsMarker = Join-Path $windowsFrontend ".jap-source-sha"
    $windowsIndex = Join-Path $windowsFrontend "index.html"
    if (-not (Test-Path $windowsIndex) -or -not (Test-Path $windowsMarker)) {
        throw "Installed desktop host does not contain the source-bound prebuilt frontend."
    }
    $markerSha = (Get-Content -Raw $windowsMarker).Trim().ToLowerInvariant()
    if ($markerSha -ne $SourceSha.ToLowerInvariant()) {
        throw "Installed desktop frontend source mismatch: $markerSha expected $SourceSha"
    }

    $sourceOutput = Invoke-Wsl @("-d", $Distro, "--exec", "wslpath", "-u", $windowsFrontend)
    $linuxSource = (($sourceOutput | Select-Object -First 1) -as [string]).Trim()
    if ([string]::IsNullOrWhiteSpace($linuxSource) -or -not $linuxSource.StartsWith('/')) {
        throw "Could not translate the packaged frontend into the configured WSL distribution."
    }

    $target = "$ManagedWorktree/frontend/control-center/dist"
    Invoke-Wsl @("-d", $Distro, "--exec", "rm", "-rf", $target) | Out-Null
    Invoke-Wsl @("-d", $Distro, "--exec", "mkdir", "-p", $target) | Out-Null
    Invoke-Wsl @("-d", $Distro, "--exec", "cp", "-a", "$linuxSource/.", $target) | Out-Null
    Invoke-Wsl @("-d", $Distro, "--exec", "test", "-f", "$target/index.html") | Out-Null
    $installedMarkerOutput = Invoke-Wsl @("-d", $Distro, "--exec", "cat", "$target/.jap-source-sha")
    $installedMarker = (($installedMarkerOutput | Select-Object -First 1) -as [string]).Trim().ToLowerInvariant()
    if ($installedMarker -ne $SourceSha.ToLowerInvariant()) {
        throw "Managed prebuilt frontend source mismatch after installation: $installedMarker expected $SourceSha"
    }
    return $target
}

$wsl = Get-Command wsl.exe -ErrorAction SilentlyContinue
if (-not $wsl) {
    throw "WSL is required to install JAP Control Center."
}

if ([string]::IsNullOrWhiteSpace($WslInstalledRunnerPath)) {
    throw "WSL installed runner path is required. Run scripts/install_jap_windows_control_center.sh from WSL."
}
$WslInstalledRunnerPath = $WslInstalledRunnerPath.Trim()
if (-not $WslInstalledRunnerPath.StartsWith('/')) {
    throw "WSL installed runner path must be an absolute Linux path."
}

if ([string]::IsNullOrWhiteSpace($WslDistro)) {
    $resolved = Invoke-Wsl @("--", "bash", "-lc", 'printf "%s" "$WSL_DISTRO_NAME"')
    $WslDistro = (($resolved | Select-Object -First 1) -as [string]).Trim()
}
if ([string]::IsNullOrWhiteSpace($WslDistro)) {
    throw "Could not resolve the default WSL distribution. Pass -WslDistro explicitly."
}

if ([string]::IsNullOrWhiteSpace($WslProjectRoot)) {
    $resolved = Invoke-Wsl @("-d", $WslDistro, "--", "bash", "-lc", 'printf "%s" "$HOME/projects/job-application-pipeline"')
    $WslProjectRoot = (($resolved | Select-Object -First 1) -as [string]).Trim()
}
if ([string]::IsNullOrWhiteSpace($WslProjectRoot)) {
    throw "Could not resolve the canonical JAP project root in WSL."
}

$top = Invoke-Wsl @("-d", $WslDistro, "--", "git", "-C", $WslProjectRoot, "rev-parse", "--show-toplevel")
$resolvedTop = (($top | Select-Object -First 1) -as [string]).Trim()
if ($resolvedTop -ne $WslProjectRoot.TrimEnd('/')) {
    throw "Configured WSL project root is not the JAP repository top level."
}

$originOutput = Invoke-Wsl @("-d", $WslDistro, "--", "git", "-C", $WslProjectRoot, "remote", "get-url", "origin")
$origin = (($originOutput | Select-Object -First 1) -as [string]).Trim()
if ($origin -notmatch [regex]::Escape($ExpectedOrigin)) {
    throw "WSL project origin does not match the JAP repository."
}

# Fetch public product code over HTTPS so installation does not depend on SSH port 22.
# `origin` remains the repository identity authority and is never rewritten here.
Invoke-Wsl @("-d", $WslDistro, "--", "git", "-C", $WslProjectRoot, "fetch", "--no-tags", $ReadOnlyFetchUrl, "main") | Out-Null
$shaOutput = Invoke-Wsl @("-d", $WslDistro, "--", "git", "-C", $WslProjectRoot, "rev-parse", "FETCH_HEAD")
$fetchedMain = (($shaOutput | Select-Object -First 1) -as [string]).Trim()
if ($fetchedMain -notmatch '^[0-9a-f]{40}$') {
    throw "Could not resolve an exact GitHub main SHA for JAP."
}

if ([string]::IsNullOrWhiteSpace($PinnedSha)) {
    $pinnedSha = $fetchedMain
}
else {
    $PinnedSha = $PinnedSha.Trim().ToLowerInvariant()
    if ($PinnedSha -notmatch '^[0-9a-f]{40}$') {
        throw "Requested pinned JAP SHA is invalid: $PinnedSha"
    }
    Invoke-Wsl @("-d", $WslDistro, "--", "git", "-C", $WslProjectRoot, "cat-file", "-e", "$PinnedSha^{commit}") | Out-Null
    & wsl.exe -d $WslDistro -- git -C $WslProjectRoot merge-base --is-ancestor $PinnedSha $fetchedMain
    if ($LASTEXITCODE -ne 0) {
        throw "Requested pinned JAP SHA is not an ancestor of current GitHub main: $PinnedSha"
    }
    $pinnedSha = $PinnedSha
}

$homeOutput = Invoke-Wsl @("-d", $WslDistro, "--", "bash", "-lc", 'printf "%s" "$HOME"')
$wslHome = (($homeOutput | Select-Object -First 1) -as [string]).Trim()
if ([string]::IsNullOrWhiteSpace($wslHome)) {
    throw "Could not resolve the WSL home directory."
}
$managedWorktree = "$wslHome/.local/share/jap-control-center/runtime"
$wslStateRoot = "$wslHome/.local/state/jap-control-center"

$sourceLauncher = Join-Path $PSScriptRoot "JAP-Control-Center.ps1"
$sourceStopper = Join-Path $PSScriptRoot "Stop-JAP-Control-Center.ps1"
$sourceApplier = Join-Path $PSScriptRoot "Apply-JAP-Control-Center-Update.ps1"
$sourceRunner = Join-Path $PSScriptRoot "scripts\run_jap_windows_control_center.sh"
$desktopVersionPath = Join-Path $PSScriptRoot "windows\JAP.ControlCenter.Desktop\VERSION"
$compatibilityPath = Join-Path $PSScriptRoot "windows\JAP.ControlCenter.Desktop\UPDATE_COMPATIBILITY.json"
foreach ($required in @($sourceLauncher, $sourceStopper, $sourceApplier, $sourceRunner, $desktopVersionPath, $compatibilityPath)) {
    if (-not (Test-Path $required)) {
        throw "Installer source is missing: $required"
    }
}
$desktopHostVersion = (Get-Content -Raw $desktopVersionPath).Trim()
$compatibility = Get-Content -Raw $compatibilityPath | ConvertFrom-Json
if ($compatibility.policy -ne "latest_direct" -or $compatibility.compatibility_line -ne $CompatibilityLine -or $compatibility.installer_schema -ne $InstallSchema) {
    throw "Desktop host update compatibility contract is invalid."
}
if ($desktopHostVersion -notmatch '^1\.\d+\.\d+$') {
    throw "Desktop host version is outside compatibility line 1: $desktopHostVersion"
}

New-Item -ItemType Directory -Force -Path $InstallRoot | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $InstallRoot "state") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $InstallRoot "logs") | Out-Null

# WINAPP-018 removes the old separately launchable updater surface. The product
# update coordinator in JAP.ControlCenter.Desktop remains the only user-facing
# update entrypoint; Apply-JAP-Control-Center-Update.ps1 is an internal helper
# invoked only after explicit consent from the main application.
Remove-Item -Force $LegacyStableUpdater -ErrorAction SilentlyContinue
Copy-Item -Force $sourceLauncher $StableLauncher
Copy-Item -Force $sourceStopper $StableStopper
Copy-Item -Force $sourceApplier $StableApplier
Copy-Item -Force $sourceRunner $StableRunner

# Prepare immutable product code and frontend before the user-facing host restarts.
# Interactive startup therefore never needs npm/network/build work for a released app.
Prepare-ManagedWorktree $WslDistro $WslProjectRoot $managedWorktree $wslHome $pinnedSha
$desktopHost = Install-DesktopHost $desktopHostVersion $DesktopHostArchivePath $DesktopHostChecksumPath $pinnedSha
if (-not (Test-Path $DesktopHostExe)) {
    throw "Installed JAP desktop host executable is missing: $DesktopHostExe"
}
$wslFrontendDist = Install-SourceBoundFrontend $WslDistro $managedWorktree $pinnedSha

Write-JsonAtomic $CurrentPath @{
    schema = $InstallSchema
    repository_id = $ExpectedRepositoryId
    repository = $ExpectedOrigin
    pinned_sha = $pinnedSha
    wsl_distro = $WslDistro
    wsl_project_root = $WslProjectRoot
    managed_worktree = $managedWorktree
    wsl_state_root = $wslStateRoot
    wsl_installed_runner_path = $WslInstalledRunnerPath
    wsl_frontend_dist = $wslFrontendDist
    port = $Port
    desktop_host = "webview2_winforms"
    desktop_host_version = $desktopHost.version
    desktop_host_sha256 = $desktopHost.sha256
    desktop_host_release = $desktopHost.tag
    desktop_host_exe = $DesktopHostExe
    installed_at = [DateTime]::UtcNow.ToString("o")
    update_authority = "local_runner_staged_gui_prompt"
    update_mode = $UpdateMode
    update_surface = "integrated_main_app"
    compatibility_line = $CompatibilityLine
    startup_frontend = "prebuilt_source_bound"
    frontend_source_sha = $desktopHost.frontend_source_sha
    secrets_location = "wsl_project_env_only"
    private_documents_location = "wsl_project_private_application_sources_only"
}

$programs = Join-Path ([Environment]::GetFolderPath("StartMenu")) "Programs\JAP Control Center"
$legacyUpdateShortcut = Join-Path $programs "Update JAP Control Center.lnk"
Remove-Item -Force $legacyUpdateShortcut -ErrorAction SilentlyContinue

if (-not $NoShortcuts) {
    $powershell = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
    $stopArguments = "-NoProfile -ExecutionPolicy Bypass -File `"$StableStopper`""

    $desktop = [Environment]::GetFolderPath("Desktop")
    New-AppShortcut (Join-Path $desktop "JAP Control Center.lnk") $DesktopHostExe "" "$DesktopHostExe,0"

    New-AppShortcut (Join-Path $programs "JAP Control Center.lnk") $DesktopHostExe "" "$DesktopHostExe,0"
    New-AppShortcut (Join-Path $programs "Stop JAP Control Center.lnk") $powershell $stopArguments
}

Write-Host "JAP_CONTROL_CENTER_INSTALL=PASS"
Write-Host "INSTALL_ROOT=$InstallRoot"
Write-Host "WSL_DISTRO=$WslDistro"
Write-Host "WSL_PROJECT_ROOT=$WslProjectRoot"
Write-Host "WSL_INSTALLED_RUNNER=$WslInstalledRunnerPath"
Write-Host "PINNED_MAIN=$pinnedSha"
Write-Host "FETCH_TRANSPORT=https"
Write-Host "DESKTOP_HOST=webview2_winforms"
Write-Host "DESKTOP_HOST_VERSION=$($desktopHost.version)"
Write-Host "DESKTOP_HOST_SHA256=$($desktopHost.sha256)"
Write-Host "DESKTOP_HOST_EXE=$DesktopHostExe"
Write-Host "FRONTEND_STARTUP=prebuilt_source_bound"
Write-Host "FRONTEND_SOURCE_SHA=$($desktopHost.frontend_source_sha)"
Write-Host "WSL_FRONTEND_DIST=$wslFrontendDist"
Write-Host "UPDATE_MODE=$UpdateMode"
Write-Host "UPDATE_SURFACE=integrated_main_app"
Write-Host "UPDATE_COMPATIBILITY_LINE=$CompatibilityLine"
Write-Host "URI=http://127.0.0.1:$Port/"
Write-Host "Boundary: no .env, credentials, PostgreSQL data, CV or application documents are copied to Windows."

if (-not $NoStart) {
    Start-Process -FilePath $DesktopHostExe -WorkingDirectory $DesktopHostRoot | Out-Null
    Write-Host "JAP_CONTROL_CENTER_DESKTOP=STARTED"
}
