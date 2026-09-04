param(
    [string]$InstallRoot = (Join-Path $env:LOCALAPPDATA "JAP-Control-Center"),
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$ExpectedRepositoryId = 1230805345
$DefaultPort = 8780
$InstallRoot = [System.IO.Path]::GetFullPath($InstallRoot)
$CurrentPath = Join-Path $InstallRoot "current.json"
$RuntimePath = Join-Path $InstallRoot "state\runtime.json"
$RunnerPath = Join-Path $InstallRoot "run-jap-control-center-wsl.sh"
$LogRoot = Join-Path $InstallRoot "logs"

function Read-Json([string]$Path) {
    if (-not (Test-Path $Path)) { return $null }
    return Get-Content -Raw $Path | ConvertFrom-Json
}

function Write-JsonAtomic([string]$Path, [object]$Value) {
    $parent = Split-Path -Parent $Path
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    $temporary = "$Path.tmp"
    $Value | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 $temporary
    Move-Item -Force $temporary $Path
}

function Test-LoopbackPort([int]$Port) {
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $async = $client.BeginConnect("127.0.0.1", $Port, $null, $null)
        if (-not $async.AsyncWaitHandle.WaitOne(500)) { return $false }
        $client.EndConnect($async)
        return $true
    }
    catch {
        return $false
    }
    finally {
        $client.Close()
    }
}

function Get-JapEndpointState([string]$Uri) {
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri $Uri -TimeoutSec 3
        $server = [string]$response.Headers["Server"]
        $healthy = ($response.StatusCode -eq 200) -and ($server -match '^DeepOceanProductV1/')
        return @{ Healthy = $healthy; Server = $server; Error = $null }
    }
    catch {
        return @{ Healthy = $false; Server = ""; Error = $_.Exception.Message }
    }
}

function Open-Jap([string]$Uri) {
    if (-not $NoBrowser) {
        Start-Process $Uri | Out-Null
    }
}

$current = Read-Json $CurrentPath
if (-not $current) {
    throw "JAP Control Center is not installed. Run install-jap-control-center.ps1 first."
}
if ([int64]$current.repository_id -ne $ExpectedRepositoryId) {
    throw "JAP Control Center repository identity mismatch."
}
if ([string]::IsNullOrWhiteSpace([string]$current.wsl_distro)) {
    throw "Installed JAP configuration has no WSL distribution."
}
if ([string]::IsNullOrWhiteSpace([string]$current.wsl_project_root)) {
    throw "Installed JAP configuration has no WSL project root."
}
if ([string]::IsNullOrWhiteSpace([string]$current.managed_worktree)) {
    throw "Installed JAP configuration has no managed WSL worktree."
}
if ([string]::IsNullOrWhiteSpace([string]$current.wsl_state_root)) {
    throw "Installed JAP configuration has no managed WSL state root."
}
if ([string]$current.pinned_sha -notmatch '^[0-9a-f]{40}$') {
    throw "Installed JAP configuration has an invalid pinned SHA."
}

$port = if ($current.port) { [int]$current.port } else { $DefaultPort }
if ($port -ne $DefaultPort) {
    throw "Installed JAP port differs from the supported loopback port $DefaultPort."
}
$uri = "http://127.0.0.1:$port/"

$endpoint = Get-JapEndpointState $uri
if ($endpoint.Healthy) {
    Write-Host "JAP Control Center already running: $uri"
    Open-Jap $uri
    exit 0
}
if (Test-LoopbackPort $port) {
    throw "Port $port is already occupied by a service that is not the JAP Control Center. Refusing to start another runtime."
}

$wsl = Get-Command wsl.exe -ErrorAction SilentlyContinue
if (-not $wsl) {
    throw "WSL is required for the installed JAP Control Center."
}
if (-not (Test-Path $RunnerPath)) {
    throw "Installed WSL launcher is missing: $RunnerPath"
}

$distro = [string]$current.wsl_distro
$linuxRunner = (& $wsl.Source -d $distro -- wslpath -u $RunnerPath 2>$null | Select-Object -First 1)
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($linuxRunner)) {
    throw "Could not map the installed JAP WSL launcher into distribution '$distro'."
}
$linuxRunner = $linuxRunner.Trim()

New-Item -ItemType Directory -Force -Path $LogRoot | Out-Null
$stdoutLog = Join-Path $LogRoot "runtime.stdout.log"
$stderrLog = Join-Path $LogRoot "runtime.stderr.log"
Remove-Item -Force $stdoutLog, $stderrLog -ErrorAction SilentlyContinue

$argumentLine = (
    '-d "{0}" -- bash "{1}" "{2}" "{3}" "{4}" "{5}"' -f
    $distro,
    $linuxRunner,
    [string]$current.wsl_project_root,
    [string]$current.managed_worktree,
    [string]$current.pinned_sha,
    [string]$current.wsl_state_root
)

$process = Start-Process \
    -FilePath $wsl.Source \
    -ArgumentList $argumentLine \
    -WindowStyle Hidden \
    -RedirectStandardOutput $stdoutLog \
    -RedirectStandardError $stderrLog \
    -PassThru

Write-JsonAtomic $RuntimePath @{
    repository_id = $ExpectedRepositoryId
    wsl_client_pid = $process.Id
    pinned_sha = [string]$current.pinned_sha
    started_at = [DateTime]::UtcNow.ToString("o")
    uri = $uri
}

for ($attempt = 0; $attempt -lt 240; $attempt++) {
    Start-Sleep -Milliseconds 500
    $endpoint = Get-JapEndpointState $uri
    if ($endpoint.Healthy) {
        Write-Host "JAP Control Center: $uri"
        Write-Host "Pinned main: $($current.pinned_sha)"
        Write-Host "WSL distribution: $distro"
        Open-Jap $uri
        exit 0
    }
    $process.Refresh()
    if ($process.HasExited) { break }
}

$stderrTail = ""
if (Test-Path $stderrLog) {
    $stderrTail = ((Get-Content $stderrLog -Tail 12 -ErrorAction SilentlyContinue) -join " | ")
}
if ([string]::IsNullOrWhiteSpace($stderrTail)) {
    throw "JAP Control Center did not become ready. See $stdoutLog and $stderrLog."
}
throw "JAP Control Center did not become ready: $stderrTail"
