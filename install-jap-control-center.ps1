param(
    [string]$InstallRoot = (Join-Path $env:LOCALAPPDATA "JAP-Control-Center"),
    [string]$WslDistro,
    [string]$WslProjectRoot,
    [switch]$NoStart,
    [switch]$NoShortcuts
)

$ErrorActionPreference = "Stop"
$ExpectedRepositoryId = 1230805345
$ExpectedOrigin = "jenshaberle-dotcom/job-application-pipeline"
$ReadOnlyFetchUrl = "https://github.com/$ExpectedOrigin.git"
$Port = 8780
$InstallRoot = [System.IO.Path]::GetFullPath($InstallRoot)
$CurrentPath = Join-Path $InstallRoot "current.json"
$StableLauncher = Join-Path $InstallRoot "JAP-Control-Center.ps1"
$StableUpdater = Join-Path $InstallRoot "Update-JAP-Control-Center.ps1"
$StableStopper = Join-Path $InstallRoot "Stop-JAP-Control-Center.ps1"
$StableRunner = Join-Path $InstallRoot "run-jap-control-center-wsl.sh"

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

function New-AppShortcut([string]$Path, [string]$Target, [string]$Arguments) {
    $parent = Split-Path -Parent $Path
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($Path)
    $shortcut.TargetPath = $Target
    $shortcut.Arguments = $Arguments
    $shortcut.WorkingDirectory = $InstallRoot
    $shortcut.IconLocation = "$env:SystemRoot\System32\imageres.dll,15"
    $shortcut.Save()
}

$wsl = Get-Command wsl.exe -ErrorAction SilentlyContinue
if (-not $wsl) {
    throw "WSL is required to install JAP Control Center."
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
foreach ($required in @($sourceLauncher, $sourceUpdater, $sourceStopper, $sourceRunner)) {
    if (-not (Test-Path $required)) {
        throw "Installer source is missing: $required"
    }
}

New-Item -ItemType Directory -Force -Path $InstallRoot | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $InstallRoot "state") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $InstallRoot "logs") | Out-Null
Copy-Item -Force $sourceLauncher $StableLauncher
Copy-Item -Force $sourceUpdater $StableUpdater
Copy-Item -Force $sourceStopper $StableStopper
Copy-Item -Force $sourceRunner $StableRunner

Write-JsonAtomic $CurrentPath @{
    schema = "job_application_pipeline.windows_control_center_install.v1"
    repository_id = $ExpectedRepositoryId
    repository = $ExpectedOrigin
    pinned_sha = $pinnedSha
    wsl_distro = $WslDistro
    wsl_project_root = $WslProjectRoot
    managed_worktree = $managedWorktree
    wsl_state_root = $wslStateRoot
    port = $Port
    installed_at = [DateTime]::UtcNow.ToString("o")
    update_authority = "explicit_github_https_main"
    secrets_location = "wsl_project_env_only"
    private_documents_location = "wsl_project_private_application_sources_only"
}

if (-not $NoShortcuts) {
    $powershell = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
    $startArguments = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$StableLauncher`""
    $updateArguments = "-NoProfile -ExecutionPolicy Bypass -File `"$StableUpdater`""
    $stopArguments = "-NoProfile -ExecutionPolicy Bypass -File `"$StableStopper`""

    $desktop = [Environment]::GetFolderPath("Desktop")
    New-AppShortcut (Join-Path $desktop "JAP Control Center.lnk") $powershell $startArguments

    $programs = Join-Path ([Environment]::GetFolderPath("StartMenu")) "Programs\JAP Control Center"
    New-AppShortcut (Join-Path $programs "JAP Control Center.lnk") $powershell $startArguments
    New-AppShortcut (Join-Path $programs "Update JAP Control Center.lnk") $powershell $updateArguments
    New-AppShortcut (Join-Path $programs "Stop JAP Control Center.lnk") $powershell $stopArguments
}

Write-Host "JAP_CONTROL_CENTER_INSTALL=PASS"
Write-Host "INSTALL_ROOT=$InstallRoot"
Write-Host "WSL_DISTRO=$WslDistro"
Write-Host "WSL_PROJECT_ROOT=$WslProjectRoot"
Write-Host "PINNED_MAIN=$pinnedSha"
Write-Host "FETCH_TRANSPORT=https"
Write-Host "URI=http://127.0.0.1:$Port/"
Write-Host "Boundary: no .env, credentials, PostgreSQL data, CV or application documents are copied to Windows."

if (-not $NoStart) {
    & $StableLauncher
}
