param(
    [string]$InstallRoot = (Join-Path $env:LOCALAPPDATA "JAP-Control-Center"),
    [string]$WslDistro,
    [string]$WslProjectRoot,
    [string]$WslInstalledRunnerPath,
    [switch]$NoStart,
    [switch]$NoShortcuts
)

$ErrorActionPreference = "Stop"
$ExpectedRepositoryId = 1230805345
$ExpectedOrigin = "jenshaberle-dotcom/job-application-pipeline"
$ReadOnlyFetchUrl = "https://github.com/$ExpectedOrigin.git"
$DesktopHostAsset = "JAP-Control-Center-Desktop-win-x64.zip"
$Port = 8780
$InstallRoot = [System.IO.Path]::GetFullPath($InstallRoot)
$CurrentPath = Join-Path $InstallRoot "current.json"
$StableLauncher = Join-Path $InstallRoot "JAP-Control-Center.ps1"
$StableUpdater = Join-Path $InstallRoot "Update-JAP-Control-Center.ps1"
$StableStopper = Join-Path $InstallRoot "Stop-JAP-Control-Center.ps1"
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

function Install-DesktopHost([string]$Version) {
    if ($Version -notmatch '^\d+\.\d+\.\d+$') {
        throw "Invalid JAP desktop host version: $Version"
    }

    $tag = "jap-winapp-desktop-v$Version"
    $releaseBase = "https://github.com/$ExpectedOrigin/releases/download/$tag"
    $tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("jap-desktop-host-" + [guid]::NewGuid().ToString("N"))
    $zip = Join-Path $tempRoot $DesktopHostAsset
    $checksum = "$zip.sha256"
    $staged = Join-Path $InstallRoot ("desktop-host.staged." + $PID)
    $backup = Join-Path $InstallRoot ("desktop-host.previous." + $PID)

    New-Item -ItemType Directory -Force -Path $tempRoot | Out-Null
    try {
        Invoke-WebRequest -UseBasicParsing -Uri "$releaseBase/$DesktopHostAsset" -OutFile $zip
        Invoke-WebRequest -UseBasicParsing -Uri "$releaseBase/$DesktopHostAsset.sha256" -OutFile $checksum

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
        }
    }
    finally {
        Remove-Item -Recurse -Force $staged -ErrorAction SilentlyContinue
        Remove-Item -Recurse -Force $tempRoot -ErrorAction SilentlyContinue
    }
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
$pinnedSha = (($shaOutput | Select-Object -First 1) -as [string]).Trim()
if ($pinnedSha -notmatch '^[0-9a-f]{40}$') {
    throw "Could not resolve an exact GitHub main SHA for JAP."
}

$homeOutput = Invoke-Wsl @("-d", $WslDistro, "--", "bash", "-lc", 'printf "%s" "$HOME"')
$wslHome = (($homeOutput | Select-Object -First 1) -as [string]).Trim()
if ([string]::IsNullOrWhiteSpace($wslHome)) {
    throw "Could not resolve the WSL home directory."
}
$managedWorktree = "$wslHome/.local/share/jap-control-center/runtime"
$wslStateRoot = "$wslHome/.local/state/jap-control-center"

$sourceLauncher = Join-Path $PSScriptRoot "JAP-Control-Center.ps1"
$sourceUpdater = Join-Path $PSScriptRoot "Update-JAP-Control-Center.ps1"
$sourceStopper = Join-Path $PSScriptRoot "Stop-JAP-Control-Center.ps1"
$sourceRunner = Join-Path $PSScriptRoot "scripts\run_jap_windows_control_center.sh"
$desktopVersionPath = Join-Path $PSScriptRoot "windows\JAP.ControlCenter.Desktop\VERSION"
foreach ($required in @($sourceLauncher, $sourceUpdater, $sourceStopper, $sourceRunner, $desktopVersionPath)) {
    if (-not (Test-Path $required)) {
        throw "Installer source is missing: $required"
    }
}
$desktopHostVersion = (Get-Content -Raw $desktopVersionPath).Trim()

New-Item -ItemType Directory -Force -Path $InstallRoot | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $InstallRoot "state") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $InstallRoot "logs") | Out-Null
Copy-Item -Force $sourceLauncher $StableLauncher
Copy-Item -Force $sourceUpdater $StableUpdater
Copy-Item -Force $sourceStopper $StableStopper
Copy-Item -Force $sourceRunner $StableRunner

$desktopHost = Install-DesktopHost $desktopHostVersion
if (-not (Test-Path $DesktopHostExe)) {
    throw "Installed JAP desktop host executable is missing: $DesktopHostExe"
}

Write-JsonAtomic $CurrentPath @{
    schema = "job_application_pipeline.windows_control_center_install.v2"
    repository_id = $ExpectedRepositoryId
    repository = $ExpectedOrigin
    pinned_sha = $pinnedSha
    wsl_distro = $WslDistro
    wsl_project_root = $WslProjectRoot
    managed_worktree = $managedWorktree
    wsl_state_root = $wslStateRoot
    wsl_installed_runner_path = $WslInstalledRunnerPath
    port = $Port
    desktop_host = "webview2_winforms"
    desktop_host_version = $desktopHost.version
    desktop_host_sha256 = $desktopHost.sha256
    desktop_host_release = $desktopHost.tag
    desktop_host_exe = $DesktopHostExe
    installed_at = [DateTime]::UtcNow.ToString("o")
    update_authority = "explicit_github_https_main"
    secrets_location = "wsl_project_env_only"
    private_documents_location = "wsl_project_private_application_sources_only"
}

if (-not $NoShortcuts) {
    $powershell = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
    $updateArguments = "-NoProfile -ExecutionPolicy Bypass -File `"$StableUpdater`""
    $stopArguments = "-NoProfile -ExecutionPolicy Bypass -File `"$StableStopper`""

    $desktop = [Environment]::GetFolderPath("Desktop")
    New-AppShortcut (Join-Path $desktop "JAP Control Center.lnk") $DesktopHostExe "" "$DesktopHostExe,0"

    $programs = Join-Path ([Environment]::GetFolderPath("StartMenu")) "Programs\JAP Control Center"
    New-AppShortcut (Join-Path $programs "JAP Control Center.lnk") $DesktopHostExe "" "$DesktopHostExe,0"
    New-AppShortcut (Join-Path $programs "Update JAP Control Center.lnk") $powershell $updateArguments
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
Write-Host "URI=http://127.0.0.1:$Port/"
Write-Host "Boundary: no .env, credentials, PostgreSQL data, CV or application documents are copied to Windows."

if (-not $NoStart) {
    Start-Process -FilePath $DesktopHostExe -WorkingDirectory $DesktopHostRoot | Out-Null
    Write-Host "JAP_CONTROL_CENTER_DESKTOP=STARTED"
}
