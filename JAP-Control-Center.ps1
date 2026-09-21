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
$StopperPath = Join-Path $InstallRoot "Stop-JAP-Control-Center.ps1"
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

function Get-JapEndpointState([string]$Uri, [string]$ExpectedSha) {
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri $Uri -TimeoutSec 3
        $server = [string]$response.Headers["Server"]
        $isJap = ($response.StatusCode -eq 200) -and ($server -match '^DeepOceanProductV1/')
        $sourceRevision = ""
        $identityError = $null

        if ($isJap) {
            try {
                $infoUri = "$($Uri.TrimEnd('/'))/app-info.json"
                $infoResponse = Invoke-WebRequest -UseBasicParsing -Uri $infoUri -TimeoutSec 3
                if ($infoResponse.StatusCode -eq 200) {
                    $info = $infoResponse.Content | ConvertFrom-Json
                    $sourceRevision = ([string]$info.source_revision).Trim().ToLowerInvariant()
                }
            }
            catch {
                $identityError = $_.Exception.Message
            }
        }

        $expected = $ExpectedSha.Trim().ToLowerInvariant()
        $healthy = $isJap -and ($sourceRevision -eq $expected)
        return @{
            Healthy = $healthy
            IsJap = $isJap
            SourceRevision = $sourceRevision
            Server = $server
            Error = $identityError
        }
    }
    catch {
        return @{
            Healthy = $false
            IsJap = $false
            SourceRevision = ""
            Server = ""
            Error = $_.Exception.Message
        }
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
if ([string]::IsNullOrWhiteSpace([string]$current.wsl_installed_runner_path)) {
    throw "Installed JAP configuration has no pretranslated WSL runner path. Re-run the current installer from WSL."
}
if ([string]$current.pinned_sha -notmatch '^[0-9a-f]{40}$') {
    throw "Installed JAP configuration has an invalid pinned SHA."
}

$linuxRunner = ([string]$current.wsl_installed_runner_path).Trim()
if (-not $linuxRunner.StartsWith('/')) {
    throw "Installed JAP WSL runner path is not an absolute Linux path."
}

$port = if ($current.port) { [int]$current.port } else { $DefaultPort }
if ($port -ne $DefaultPort) {
    throw "Installed JAP port differs from the supported loopback port $DefaultPort."
}
$uri = "http://127.0.0.1:$port/"

$endpoint = Get-JapEndpointState $uri ([string]$current.pinned_sha)
if ($endpoint.Healthy) {
    Write-Host "JAP Control Center already running: $uri"
    Write-Host "Runtime source: $($endpoint.SourceRevision)"
    Open-Jap $uri
    exit 0
}

# A healthy JAP-shaped server is reusable only when it proves the exact installed
# source pin. This prevents a pre-update runtime from serving an old ignored
# frontend bundle after the desktop host has already moved to a newer release.
if ($endpoint.IsJap) {
    if (-not (Test-Path $StopperPath)) {
        throw "A stale JAP runtime is serving $uri, but the managed stopper is missing. Refusing unsafe runtime reuse."
    }

    Write-Host "JAP_CONTROL_CENTER_RUNTIME=STALE source=$($endpoint.SourceRevision) expected=$($current.pinned_sha)"
    & $StopperPath -InstallRoot $InstallRoot

    for ($attempt = 0; $attempt -lt 40; $attempt += 1) {
        if (-not (Test-LoopbackPort $port)) { break }
        Start-Sleep -Milliseconds 250
    }
    if (Test-LoopbackPort $port) {
        throw "The stale managed JAP runtime did not release port $port. Refusing to start a second runtime."
    }
}

if (Test-LoopbackPort $port) {
    throw "Port $port is already occupied by a service that is not the current JAP Control Center. Refusing to start another runtime."
}

$wsl = Get-Command wsl.exe -ErrorAction SilentlyContinue
if (-not $wsl) {
    throw "WSL is required for the installed JAP Control Center."
}
if (-not (Test-Path $RunnerPath)) {
    throw "Installed WSL launcher is missing: $RunnerPath"
}

$distro = ([string]$current.wsl_distro).Trim()

# Prove the persisted distribution and Linux runner path with a direct native
# invocation before backgrounding. The installer already used this direct form
# successfully; keeping the proof here distinguishes WSL identity/path failures
# from detached-launch command-line failures.
& $wsl.Source -d $distro --exec test -f $linuxRunner
if ($LASTEXITCODE -ne 0) {
    throw "Installed JAP WSL distribution/runner proof failed for '$distro' and '$linuxRunner'."
}

New-Item -ItemType Directory -Force -Path $LogRoot | Out-Null

# Keep runtime logs entirely inside the already-persisted Linux state root.
# Windows never translates runtime log paths with wslpath; that translation boundary
# previously proved fragile during interactive startup.
$stateRootLinux = ([string]$current.wsl_state_root).Trim().TrimEnd("/")
if (-not $stateRootLinux.StartsWith("/")) {
    throw "Installed JAP WSL state root is not an absolute Linux path."
}
$stdoutLinux = "$stateRootLinux/runtime.stdout.log"
$stderrLinux = "$stateRootLinux/runtime.stderr.log"

# Keep the Windows side short-lived and tokenized. The actual long-lived
# Product runtime is detached inside WSL with nohup+setsid, where Linux owns the
# stdout/stderr redirection and process lifetime. This avoids cmd.exe/start quoting
# and prevents the desktop host's redirected PowerShell pipes from being inherited.

$wslArgumentVector = @(
    "-d",
    $distro,
    "--exec",
    "bash",
    $linuxRunner,
    [string]$current.wsl_project_root,
    [string]$current.managed_worktree,
    [string]$current.pinned_sha,
    [string]$current.wsl_state_root,
    "launch",
    $stdoutLinux,
    $stderrLinux
)
& $wsl.Source @wslArgumentVector
if ($LASTEXITCODE -ne 0) {
    throw "Detached JAP WSL runtime handoff failed with exit code $LASTEXITCODE."
}

Write-JsonAtomic $RuntimePath @{
    repository_id = $ExpectedRepositoryId
    launch_mode = "wsl_nohup_setsid"
    pinned_sha = [string]$current.pinned_sha
    started_at = [DateTime]::UtcNow.ToString("o")
    uri = $uri
}

# Keep the launcher readiness deadline comfortably inside the native desktop
# host's 90-second hard bound. This guarantees that the launcher can surface the
# bounded WSL stdout/stderr tail instead of being killed before it reports cause.
$readinessDeadline = [DateTime]::UtcNow.AddSeconds(75)
$lastEndpointError = [string]$endpoint.Error
while ([DateTime]::UtcNow -lt $readinessDeadline) {
    Start-Sleep -Milliseconds 500
    $endpoint = Get-JapEndpointState $uri ([string]$current.pinned_sha)
    $lastEndpointError = [string]$endpoint.Error
    if ($endpoint.Healthy) {
        Write-Host "JAP Control Center: $uri"
        Write-Host "Pinned main: $($current.pinned_sha)"
        Write-Host "Runtime source: $($endpoint.SourceRevision)"
        Write-Host "WSL distribution: $distro"
        Open-Jap $uri
        exit 0
    }
}

$stdoutTail = ""
$stdoutTailOutput = & $wsl.Source -d $distro --exec tail -n 12 $stdoutLinux 2>$null
if ($LASTEXITCODE -eq 0) {
    $stdoutTail = (($stdoutTailOutput | ForEach-Object { [string]$_ }) -join " | ")
}
$stderrTail = ""
$stderrTailOutput = & $wsl.Source -d $distro --exec tail -n 12 $stderrLinux 2>$null
if ($LASTEXITCODE -eq 0) {
    $stderrTail = (($stderrTailOutput | ForEach-Object { [string]$_ }) -join " | ")
}
if (-not [string]::IsNullOrWhiteSpace($stderrTail)) {
    throw "JAP Control Center did not become ready: $stderrTail"
}
if (-not [string]::IsNullOrWhiteSpace($stdoutTail)) {
    throw "JAP Control Center did not become ready: $stdoutTail"
}
if (-not [string]::IsNullOrWhiteSpace($lastEndpointError)) {
    throw "JAP Control Center did not become ready. Last endpoint error: $lastEndpointError"
}
throw "JAP Control Center did not become ready. See WSL state logs $stdoutLinux and $stderrLinux."
