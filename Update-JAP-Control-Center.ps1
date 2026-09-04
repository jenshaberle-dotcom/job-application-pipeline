param(
    [string]$InstallRoot = (Join-Path $env:LOCALAPPDATA "JAP-Control-Center")
)

$ErrorActionPreference = "Stop"
$ExpectedRepositoryId = 1230805345
$InstallRoot = [System.IO.Path]::GetFullPath($InstallRoot)
$CurrentPath = Join-Path $InstallRoot "current.json"

function Read-Json([string]$Path) {
    if (-not (Test-Path $Path)) { return $null }
    return Get-Content -Raw $Path | ConvertFrom-Json
}

function Write-JsonAtomic([string]$Path, [object]$Value) {
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

$current = Read-Json $CurrentPath
if (-not $current) {
    throw "JAP Control Center is not installed."
}
if ([int64]$current.repository_id -ne $ExpectedRepositoryId) {
    throw "JAP Control Center repository identity mismatch."
}

$distro = [string]$current.wsl_distro
$project = [string]$current.wsl_project_root
if ([string]::IsNullOrWhiteSpace($distro) -or [string]::IsNullOrWhiteSpace($project)) {
    throw "Installed JAP WSL configuration is incomplete."
}

Invoke-Wsl @("-d", $distro, "--", "git", "-C", $project, "fetch", "origin", "main") | Out-Null
$shaOutput = Invoke-Wsl @("-d", $distro, "--", "git", "-C", $project, "rev-parse", "origin/main")
$newSha = (($shaOutput | Select-Object -First 1) -as [string]).Trim()
if ($newSha -notmatch '^[0-9a-f]{40}$') {
    throw "Could not resolve an exact origin/main SHA for JAP."
}

$oldSha = [string]$current.pinned_sha
if ($oldSha -eq $newSha) {
    Write-Host "JAP_CONTROL_CENTER_UPDATE=NO_CHANGE"
    Write-Host "PINNED_MAIN=$newSha"
    exit 0
}

$current.pinned_sha = $newSha
$current.updated_at = [DateTime]::UtcNow.ToString("o")
Write-JsonAtomic $CurrentPath $current

Write-Host "JAP_CONTROL_CENTER_UPDATE=STAGED"
Write-Host "OLD_MAIN=$oldSha"
Write-Host "NEW_MAIN=$newSha"
Write-Host "The new exact main is used on the next managed start. Running unmanaged/manual JAP sessions are never killed by the updater."
