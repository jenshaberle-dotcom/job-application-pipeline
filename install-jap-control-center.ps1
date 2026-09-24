param(
    [string]$InstallRoot = (Join-Path $env:LOCALAPPDATA "JAP-Control-Center"),
    [string]$WslDistro,
    [string]$WslProjectRoot,
    [string]$PinnedSha,
    [string]$DesktopHostArchivePath,
    [string]$DesktopHostChecksumPath,
    [string]$RuntimeArchivePath,
    [string]$RuntimeChecksumPath,
    [switch]$NoStart,
    [switch]$NoShortcuts
)

$ErrorActionPreference = "Stop"
$ExpectedRepositoryId = 1230805345
$ExpectedOrigin = "jenshaberle-dotcom/job-application-pipeline"
$ReadOnlyFetchUrl = "https://github.com/$ExpectedOrigin.git"
$InstallSchema = "job_application_pipeline.windows_control_center_install.v3"
$CompatibilityLine = "cgkb-product-local-1"
$UpdateGeneration = "cgkb_product_local_v1"
$UpdateMode = "product_local_stage_before_consent_v2"
$ReleaseNamespace = "jap-winapp-product-v"
$DesktopAsset = "JAP-Control-Center-Desktop-win-x64.zip"
$RuntimeAsset = "JAP-Control-Center-Runtime.zip"
$Port = 8780

$InstallRoot = [System.IO.Path]::GetFullPath($InstallRoot)
$CurrentPath = Join-Path $InstallRoot "current.json"
$DesktopHostRoot = Join-Path $InstallRoot "desktop-host"
$DesktopHostExe = Join-Path $DesktopHostRoot "JAP.ControlCenter.Desktop.exe"
$RuntimeRoot = Join-Path $InstallRoot "runtime"
$StableStopper = Join-Path $InstallRoot "Stop-JAP-Control-Center.ps1"

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

function Get-VerifiedPayload(
    [string]$ReleaseBase,
    [string]$AssetName,
    [string]$ArchiveOverride,
    [string]$ChecksumOverride,
    [string]$TempRoot
) {
    $useOverride = -not [string]::IsNullOrWhiteSpace($ArchiveOverride) -or -not [string]::IsNullOrWhiteSpace($ChecksumOverride)
    if ($useOverride) {
        if ([string]::IsNullOrWhiteSpace($ArchiveOverride) -or [string]::IsNullOrWhiteSpace($ChecksumOverride)) {
            throw "Archive and checksum overrides must be supplied together for $AssetName."
        }
        $archive = [System.IO.Path]::GetFullPath($ArchiveOverride)
        $checksum = [System.IO.Path]::GetFullPath($ChecksumOverride)
    }
    else {
        $archive = Join-Path $TempRoot $AssetName
        $checksum = "$archive.sha256"
        Invoke-WebRequest -UseBasicParsing -Uri "$ReleaseBase/$AssetName" -OutFile $archive
        Invoke-WebRequest -UseBasicParsing -Uri "$ReleaseBase/$AssetName.sha256" -OutFile $checksum
    }

    if (-not (Test-Path $archive -PathType Leaf) -or -not (Test-Path $checksum -PathType Leaf)) {
        throw "Release payload is incomplete for $AssetName."
    }

    $expected = ((Get-Content -Raw $checksum).Trim() -split '\s+')[0].ToLowerInvariant()
    if ($expected -notmatch '^[0-9a-f]{64}$') {
        throw "Release checksum is invalid for $AssetName."
    }
    $actual = (Get-FileHash $archive -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne $expected) {
        throw "Release checksum mismatch for $AssetName."
    }

    return @{
        archive = $archive
        checksum = $checksum
        sha256 = $actual
    }
}

function Assert-BundleIdentity(
    [string]$DesktopStage,
    [string]$RuntimeStage,
    [string]$Version,
    [string]$SourceSha
) {
    $buildInfoPath = Join-Path $DesktopStage "build-info.json"
    $runtimeInfoPath = Join-Path $RuntimeStage "runtime-info.json"
    if (-not (Test-Path $buildInfoPath) -or -not (Test-Path $runtimeInfoPath)) {
        throw "Product release identity metadata is incomplete."
    }

    $build = Get-Content -Raw $buildInfoPath | ConvertFrom-Json
    if ($build.schema -ne "job_application_pipeline.desktop_host_build.v2" -or
        $build.version -ne $Version -or
        ([string]$build.source_sha).ToLowerInvariant() -ne $SourceSha -or
        $build.compatibility_line -ne $CompatibilityLine -or
        $build.update_generation -ne $UpdateGeneration) {
        throw "Desktop product identity mismatch."
    }

    $runtime = Get-Content -Raw $runtimeInfoPath | ConvertFrom-Json
    if ($runtime.schema -ne "job_application_pipeline.runtime_bundle.v1" -or
        $runtime.version -ne $Version -or
        ([string]$runtime.source_sha).ToLowerInvariant() -ne $SourceSha -or
        $runtime.compatibility_line -ne $CompatibilityLine -or
        $runtime.update_generation -ne $UpdateGeneration) {
        throw "Runtime product identity mismatch."
    }

    foreach ($required in @(
        (Join-Path $DesktopStage "JAP.ControlCenter.Desktop.exe"),
        (Join-Path $RuntimeStage "scripts\run_product_v1_live_demo.py"),
        (Join-Path $RuntimeStage "scripts\run_jap_windows_control_center.sh"),
        (Join-Path $RuntimeStage "scripts\ensure_pinned_local_oss_runtime.sh"),
        (Join-Path $RuntimeStage "vendor\codex\codex"),
        (Join-Path $RuntimeStage "vendor\codex\codex-info.json"),
        (Join-Path $RuntimeStage "frontend\control-center\dist\index.html"),
        (Join-Path $RuntimeStage "frontend\control-center\dist\.jap-source-sha")
    )) {
        if (-not (Test-Path $required -PathType Leaf)) {
            throw "Product release is missing required file: $required"
        }
    }

    $marker = (Get-Content -Raw (Join-Path $RuntimeStage "frontend\control-center\dist\.jap-source-sha")).Trim().ToLowerInvariant()
    if ($marker -ne $SourceSha) {
        throw "Runtime frontend source marker mismatch."
    }

    $runtimeShellScripts = @(Get-ChildItem -Path (Join-Path $RuntimeStage "scripts") -Filter "*.sh" -File -Recurse)
    if ($runtimeShellScripts.Count -eq 0) {
        throw "Product runtime contains no shell scripts."
    }
    foreach ($shellScript in $runtimeShellScripts) {
        $bytes = [System.IO.File]::ReadAllBytes($shellScript.FullName)
        if ($bytes -contains 13) {
            throw "Product runtime shell script contains CR bytes: $($shellScript.FullName)"
        }
    }
}

$wsl = Get-Command wsl.exe -ErrorAction SilentlyContinue
if (-not $wsl) {
    throw "WSL is required to install JAP Control Center."
}

if ([string]::IsNullOrWhiteSpace($WslDistro)) {
    $resolved = Invoke-Wsl @("--exec", "bash", "-lc", 'printf "%s" "$WSL_DISTRO_NAME"')
    $WslDistro = (($resolved | Select-Object -First 1) -as [string]).Trim()
}
if ([string]::IsNullOrWhiteSpace($WslDistro)) {
    throw "Could not resolve the WSL distribution."
}

if ([string]::IsNullOrWhiteSpace($WslProjectRoot)) {
    $resolved = Invoke-Wsl @("-d", $WslDistro, "--exec", "bash", "-lc", 'printf "%s" "$HOME/projects/job-application-pipeline"')
    $WslProjectRoot = (($resolved | Select-Object -First 1) -as [string]).Trim()
}
if ([string]::IsNullOrWhiteSpace($WslProjectRoot) -or -not $WslProjectRoot.StartsWith('/')) {
    throw "Could not resolve the canonical JAP WSL project root."
}

$top = Invoke-Wsl @("-d", $WslDistro, "--exec", "git", "-C", $WslProjectRoot, "rev-parse", "--show-toplevel")
if ((($top | Select-Object -First 1) -as [string]).Trim() -ne $WslProjectRoot.TrimEnd('/')) {
    throw "Configured WSL project root is not the JAP repository top level."
}
$origin = Invoke-Wsl @("-d", $WslDistro, "--exec", "git", "-C", $WslProjectRoot, "remote", "get-url", "origin")
if (((($origin | Select-Object -First 1) -as [string]).Trim()) -notmatch [regex]::Escape($ExpectedOrigin)) {
    throw "WSL project origin does not match the JAP repository."
}

Invoke-Wsl @("-d", $WslDistro, "--exec", "git", "-C", $WslProjectRoot, "fetch", "--no-tags", $ReadOnlyFetchUrl, "main") | Out-Null
$fetched = Invoke-Wsl @("-d", $WslDistro, "--exec", "git", "-C", $WslProjectRoot, "rev-parse", "FETCH_HEAD")
$fetchedMain = (($fetched | Select-Object -First 1) -as [string]).Trim().ToLowerInvariant()
if ($fetchedMain -notmatch '^[0-9a-f]{40}$') {
    throw "Could not resolve exact GitHub main source for JAP."
}

if ([string]::IsNullOrWhiteSpace($PinnedSha)) {
    $PinnedSha = $fetchedMain
}
else {
    $PinnedSha = $PinnedSha.Trim().ToLowerInvariant()
    if ($PinnedSha -notmatch '^[0-9a-f]{40}$') {
        throw "Requested pinned JAP SHA is invalid."
    }
    & wsl.exe -d $WslDistro --exec git -C $WslProjectRoot merge-base --is-ancestor $PinnedSha $fetchedMain
    if ($LASTEXITCODE -ne 0) {
        throw "Requested pinned JAP SHA is not an ancestor of current GitHub main."
    }
}

$versionPath = Join-Path $PSScriptRoot "windows\JAP.ControlCenter.Desktop\VERSION"
$compatibilityPath = Join-Path $PSScriptRoot "windows\JAP.ControlCenter.Desktop\UPDATE_COMPATIBILITY.json"
$sourceStopper = Join-Path $PSScriptRoot "Stop-JAP-Control-Center.ps1"
foreach ($required in @($versionPath, $compatibilityPath, $sourceStopper)) {
    if (-not (Test-Path $required -PathType Leaf)) {
        throw "Bootstrap source is missing: $required"
    }
}

$Version = (Get-Content -Raw $versionPath).Trim()
if ([version]$Version -lt [version]"1.0.65") {
    throw "CGKB product-local bootstrap requires version 1.0.65 or newer."
}
$compatibility = Get-Content -Raw $compatibilityPath | ConvertFrom-Json
if ($compatibility.schema -ne "job_application_pipeline.windows_update_compatibility.v2" -or
    $compatibility.policy -ne "product_local_latest_direct" -or
    $compatibility.compatibility_line -ne $CompatibilityLine -or
    $compatibility.update_generation -ne $UpdateGeneration -or
    $compatibility.release_namespace -ne $ReleaseNamespace -or
    $compatibility.installer_schema -ne $InstallSchema) {
    throw "CGKB product-local compatibility contract is invalid."
}

foreach ($process in @(Get-Process -Name "JAP.ControlCenter.Desktop" -ErrorAction SilentlyContinue)) {
    try {
        if ($process.Path -and ([System.IO.Path]::GetFullPath($process.Path)).StartsWith($InstallRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Close JAP Control Center before running the product-local bootstrap bridge."
        }
    }
    catch [System.ComponentModel.Win32Exception] { }
}

$tag = "$ReleaseNamespace$Version"
$releaseBase = "https://github.com/$ExpectedOrigin/releases/download/$tag"
$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("jap-product-bootstrap-" + [guid]::NewGuid().ToString("N"))
$desktopStage = Join-Path $InstallRoot ("desktop-host.staged." + $PID)
$runtimeStage = Join-Path $InstallRoot ("runtime.staged." + $PID)
$rollbackRoot = Join-Path $InstallRoot ("rollback\bootstrap-" + $PID)
$desktopBackup = Join-Path $rollbackRoot "desktop-host"
$runtimeBackup = Join-Path $rollbackRoot "runtime"
$previousCurrent = if (Test-Path $CurrentPath) { Get-Content -Raw $CurrentPath } else { $null }

New-Item -ItemType Directory -Force -Path $InstallRoot | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $InstallRoot "state") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $InstallRoot "logs") | Out-Null
New-Item -ItemType Directory -Force -Path $tempRoot | Out-Null

try {
    $desktopPayload = Get-VerifiedPayload $releaseBase $DesktopAsset $DesktopHostArchivePath $DesktopHostChecksumPath $tempRoot
    $runtimePayload = Get-VerifiedPayload $releaseBase $RuntimeAsset $RuntimeArchivePath $RuntimeChecksumPath $tempRoot

    Remove-Item -Recurse -Force $desktopStage, $runtimeStage, $rollbackRoot -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Force -Path $desktopStage, $runtimeStage, $rollbackRoot | Out-Null
    Expand-Archive -Path $desktopPayload.archive -DestinationPath $desktopStage -Force
    Expand-Archive -Path $runtimePayload.archive -DestinationPath $runtimeStage -Force
    Assert-BundleIdentity $desktopStage $runtimeStage $Version $PinnedSha

    $wslInstall = Invoke-Wsl @("-d", $WslDistro, "--exec", "wslpath", "-a", "-u", $InstallRoot)
    $wslInstallRoot = (($wslInstall | Select-Object -First 1) -as [string]).Trim()
    if ([string]::IsNullOrWhiteSpace($wslInstallRoot) -or -not $wslInstallRoot.StartsWith('/')) {
        throw "Could not resolve WSL path for JAP install root."
    }
    $wslRuntimeRoot = "$($wslInstallRoot.TrimEnd('/'))/runtime"
    $wslRuntimeRunner = "$wslRuntimeRoot/scripts/run_jap_windows_control_center.sh"
    $wslHomeOutput = Invoke-Wsl @("-d", $WslDistro, "--exec", "bash", "-lc", 'printf "%s" "$HOME"')
    $wslHome = (($wslHomeOutput | Select-Object -First 1) -as [string]).Trim()
    $wslStateRoot = "$wslHome/.local/state/jap-control-center"

    if (Test-Path $DesktopHostRoot) { Move-Item $DesktopHostRoot $desktopBackup }
    if (Test-Path $RuntimeRoot) { Move-Item $RuntimeRoot $runtimeBackup }
    Move-Item $desktopStage $DesktopHostRoot
    Move-Item $runtimeStage $RuntimeRoot

    Copy-Item -Force $sourceStopper $StableStopper

    Write-JsonAtomic $CurrentPath @{
        schema = $InstallSchema
        repository_id = $ExpectedRepositoryId
        repository = $ExpectedOrigin
        pinned_sha = $PinnedSha
        wsl_distro = $WslDistro
        wsl_project_root = $WslProjectRoot
        wsl_runtime_root = $wslRuntimeRoot
        wsl_runtime_runner_path = $wslRuntimeRunner
        wsl_state_root = $wslStateRoot
        port = $Port
        desktop_host = "webview2_winforms"
        desktop_host_version = $Version
        desktop_host_sha256 = $desktopPayload.sha256
        desktop_host_release = $tag
        runtime_bundle_sha256 = $runtimePayload.sha256
        update_authority = "product_local_update_agent_v2"
        update_mode = $UpdateMode
        update_surface = "integrated_main_app"
        update_generation = $UpdateGeneration
        release_namespace = $ReleaseNamespace
        compatibility_line = $CompatibilityLine
        installed_at = [DateTime]::UtcNow.ToString("o")
        secrets_location = "wsl_project_env_only"
        private_documents_location = "wsl_project_private_application_sources_only"
    }

    foreach ($legacy in @(
        "Update-JAP-Control-Center.ps1",
        "Apply-JAP-Control-Center-Update.ps1",
        "run-jap-control-center-wsl.sh",
        "JAP-Control-Center.ps1"
    )) {
        Remove-Item -Force (Join-Path $InstallRoot $legacy) -ErrorAction SilentlyContinue
    }
    foreach ($state in @(
        "pending-update.json",
        "accepted-update.json",
        "update-snooze.json",
        "update-result.json"
    )) {
        Remove-Item -Force (Join-Path $InstallRoot "state\$state") -ErrorAction SilentlyContinue
    }

    $programs = Join-Path ([Environment]::GetFolderPath("StartMenu")) "Programs\JAP Control Center"
    Remove-Item -Force (Join-Path $programs "Update JAP Control Center.lnk") -ErrorAction SilentlyContinue

    if (-not $NoShortcuts) {
        $desktop = [Environment]::GetFolderPath("Desktop")
        New-AppShortcut (Join-Path $desktop "JAP Control Center.lnk") $DesktopHostExe "" "$DesktopHostExe,0"
        New-AppShortcut (Join-Path $programs "JAP Control Center.lnk") $DesktopHostExe "" "$DesktopHostExe,0"
        $powershell = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
        $stopArguments = "-NoProfile -ExecutionPolicy RemoteSigned -File `"$StableStopper`""
        New-AppShortcut (Join-Path $programs "Stop JAP Control Center.lnk") $powershell $stopArguments
    }

    Remove-Item -Recurse -Force $rollbackRoot -ErrorAction SilentlyContinue

    Write-Host "JAP_CONTROL_CENTER_BOOTSTRAP_BRIDGE=PASS"
    Write-Host "DESKTOP_HOST_VERSION=$Version"
    Write-Host "PINNED_MAIN=$PinnedSha"
    Write-Host "UPDATE_GENERATION=$UpdateGeneration"
    Write-Host "RELEASE_NAMESPACE=$ReleaseNamespace"
    Write-Host "WSL_RUNTIME_ROOT=$wslRuntimeRoot"
    Write-Host "URI=http://127.0.0.1:$Port/"

    if (-not $NoStart) {
        Start-Process -FilePath $DesktopHostExe -WorkingDirectory $DesktopHostRoot | Out-Null
        Write-Host "JAP_CONTROL_CENTER_DESKTOP=STARTED"
    }
}
catch {
    try {
        if (Test-Path $DesktopHostRoot) { Remove-Item -Recurse -Force $DesktopHostRoot -ErrorAction SilentlyContinue }
        if (Test-Path $RuntimeRoot) { Remove-Item -Recurse -Force $RuntimeRoot -ErrorAction SilentlyContinue }
        if (Test-Path $desktopBackup) { Move-Item $desktopBackup $DesktopHostRoot }
        if (Test-Path $runtimeBackup) { Move-Item $runtimeBackup $RuntimeRoot }
        if ($null -ne $previousCurrent) {
            $tmp = "$CurrentPath.rollback.tmp"
            Set-Content -Encoding UTF8 -Path $tmp -Value $previousCurrent
            Move-Item -Force $tmp $CurrentPath
        }
    }
    catch { }
    throw
}
finally {
    Remove-Item -Recurse -Force $desktopStage, $runtimeStage, $tempRoot -ErrorAction SilentlyContinue
}
