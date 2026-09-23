param(
    [string]$InstallRoot = (Join-Path $env:LOCALAPPDATA "JAP-Control-Center")
)

$ErrorActionPreference = "Stop"
$ExpectedRepositoryId = 1230805345
$InstallRoot = [System.IO.Path]::GetFullPath($InstallRoot)
$CurrentPath = Join-Path $InstallRoot "current.json"

$current = Get-Content -Raw $CurrentPath | ConvertFrom-Json
if (-not $current) {
    throw "JAP Control Center is not installed."
}
if ([int64]$current.repository_id -ne $ExpectedRepositoryId) {
    throw "JAP Control Center repository identity mismatch."
}
if ([string]$current.schema -ne "job_application_pipeline.windows_control_center_install.v3") {
    throw "JAP Control Center is not on the CGKB product-local install generation."
}
if ([string]$current.update_generation -ne "cgkb_product_local_v1") {
    throw "JAP Control Center update generation mismatch."
}

$linuxRunner = ([string]$current.wsl_runtime_runner_path).Trim()
$runtimeRoot = ([string]$current.wsl_runtime_root).Trim()
$projectRoot = ([string]$current.wsl_project_root).Trim()
$stateRoot = ([string]$current.wsl_state_root).Trim()
$distro = ([string]$current.wsl_distro).Trim()
foreach ($value in @($linuxRunner, $runtimeRoot, $projectRoot, $stateRoot)) {
    if ([string]::IsNullOrWhiteSpace($value) -or -not $value.StartsWith('/')) {
        throw "Installed JAP WSL runtime paths are incomplete or invalid."
    }
}

$wsl = Get-Command wsl.exe -ErrorAction SilentlyContinue
if (-not $wsl) {
    throw "WSL is required to stop JAP Control Center."
}

$stopArguments = @(
    "-d",
    $distro,
    "--exec",
    "bash",
    $linuxRunner,
    $projectRoot,
    $runtimeRoot,
    [string]$current.pinned_sha,
    $stateRoot,
    "--stop"
)
& $wsl.Source @stopArguments
if ($LASTEXITCODE -ne 0) {
    throw "Managed JAP Control Center stop failed."
}

Remove-Item -Force (Join-Path $InstallRoot "state\runtime.json") -ErrorAction SilentlyContinue
Write-Host "JAP_CONTROL_CENTER_STOP=COMPLETE"
Write-Host "Only the runtime proven by the immutable runtime-bundle PID contract is eligible for termination."
