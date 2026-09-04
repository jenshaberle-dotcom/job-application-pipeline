param(
    [string]$InstallRoot = (Join-Path $env:LOCALAPPDATA "JAP-Control-Center")
)

$ErrorActionPreference = "Stop"
$ExpectedRepositoryId = 1230805345
$InstallRoot = [System.IO.Path]::GetFullPath($InstallRoot)
$CurrentPath = Join-Path $InstallRoot "current.json"
$RunnerPath = Join-Path $InstallRoot "run-jap-control-center-wsl.sh"

function Read-Json([string]$Path) {
    if (-not (Test-Path $Path)) { return $null }
    return Get-Content -Raw $Path | ConvertFrom-Json
}

$current = Read-Json $CurrentPath
if (-not $current) {
    throw "JAP Control Center is not installed."
}
if ([int64]$current.repository_id -ne $ExpectedRepositoryId) {
    throw "JAP Control Center repository identity mismatch."
}
if (-not (Test-Path $RunnerPath)) {
    throw "Installed WSL launcher is missing: $RunnerPath"
}

$wsl = Get-Command wsl.exe -ErrorAction SilentlyContinue
if (-not $wsl) {
    throw "WSL is required to stop JAP Control Center."
}
$distro = [string]$current.wsl_distro
$linuxRunner = (& $wsl.Source -d $distro -- wslpath -u $RunnerPath 2>$null | Select-Object -First 1)
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($linuxRunner)) {
    throw "Could not map the installed JAP WSL launcher."
}

$stopArguments = @(
    "-d",
    $distro,
    "--",
    "bash",
    $linuxRunner.Trim(),
    [string]$current.wsl_project_root,
    [string]$current.managed_worktree,
    [string]$current.pinned_sha,
    [string]$current.wsl_state_root,
    "--stop"
)
& $wsl.Source @stopArguments
if ($LASTEXITCODE -ne 0) {
    throw "Managed JAP Control Center stop failed."
}

Remove-Item -Force (Join-Path $InstallRoot "state\runtime.json") -ErrorAction SilentlyContinue
Write-Host "JAP_CONTROL_CENTER_STOP=COMPLETE"
Write-Host "Only the runtime proven by the managed WSL PID contract is eligible for termination."
