[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [string]$Hostname = $env:JAP_DEMO_REMOTE_HOSTNAME,

    [ValidateRange(10, 120)]
    [int]$AccessProbeTimeoutSeconds = 30,

    [switch]$Stop
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Origin = "http://127.0.0.1:8780"
$StateRoot = Join-Path $env:LOCALAPPDATA "JAP-Control-Center\demo-remote"
$StateFile = Join-Path $StateRoot "cloudflared-process.json"

function Stop-WithReason {
    param([Parameter(Mandatory = $true)][string]$Reason)
    Write-Error "JAP_CLASSIC_REMOTE_DEMO=BLOCKED reason=$Reason"
    exit 2
}

function Get-CloudflaredPath {
    $command = Get-Command "cloudflared.exe" -ErrorAction SilentlyContinue
    if ($null -eq $command) {
        $command = Get-Command "cloudflared" -ErrorAction SilentlyContinue
    }
    if ($null -eq $command -or [string]::IsNullOrWhiteSpace($command.Source)) {
        Stop-WithReason "cloudflared_not_found"
    }
    return [System.IO.Path]::GetFullPath($command.Source)
}

function Get-ManagedTunnelProcess {
    if (-not (Test-Path -LiteralPath $StateFile -PathType Leaf)) {
        return $null
    }

    try {
        $state = Get-Content -LiteralPath $StateFile -Raw -Encoding UTF8 | ConvertFrom-Json
        $pidValue = [int]$state.pid
        $expectedPath = [System.IO.Path]::GetFullPath([string]$state.cloudflared_path)
        $process = Get-Process -Id $pidValue -ErrorAction Stop
        $actualPath = [System.IO.Path]::GetFullPath($process.Path)

        if (
            $process.ProcessName -ne "cloudflared" -or
            -not [string]::Equals(
                $actualPath,
                $expectedPath,
                [System.StringComparison]::OrdinalIgnoreCase
            )
        ) {
            return $null
        }

        return $process
    }
    catch {
        return $null
    }
}

function Stop-ManagedTunnel {
    $process = Get-ManagedTunnelProcess
    if ($null -eq $process) {
        Remove-Item -LiteralPath $StateFile -Force -ErrorAction SilentlyContinue
        Write-Host "JAP_CLASSIC_REMOTE_DEMO_STOP=NO_MANAGED_TUNNEL"
        return
    }

    Stop-Process -Id $process.Id -ErrorAction Stop
    try {
        $process.WaitForExit(10000) | Out-Null
    }
    catch {
        Stop-WithReason "cloudflared_stop_timeout"
    }

    Remove-Item -LiteralPath $StateFile -Force -ErrorAction SilentlyContinue
    Write-Host "JAP_CLASSIC_REMOTE_DEMO_STOP=PASS"
}

function New-NoRedirectHttpClient {
    Add-Type -AssemblyName System.Net.Http
    $handler = New-Object System.Net.Http.HttpClientHandler
    $handler.AllowAutoRedirect = $false
    $client = New-Object System.Net.Http.HttpClient($handler)
    $client.Timeout = [TimeSpan]::FromSeconds(5)
    return $client
}

function Assert-LocalJapReady {
    $client = New-NoRedirectHttpClient
    try {
        $response = $client.GetAsync("$Origin/healthz").GetAwaiter().GetResult()
        $status = [int]$response.StatusCode
        if ($status -ne 200) {
            Stop-WithReason "local_health_http_$status"
        }

        $body = $response.Content.ReadAsStringAsync().GetAwaiter().GetResult()
        $payload = $body | ConvertFrom-Json
        if ([string]$payload.status -ne "ok") {
            Stop-WithReason "local_health_payload_not_ok"
        }
    }
    catch {
        Stop-WithReason "local_jap_not_ready"
    }
    finally {
        $client.Dispose()
    }
}

function Test-AccessChallenge {
    param([Parameter(Mandatory = $true)][string]$RemoteHostname)

    $client = New-NoRedirectHttpClient
    try {
        $response = $client.GetAsync("https://$RemoteHostname/healthz").GetAwaiter().GetResult()
        $status = [int]$response.StatusCode

        if ($status -eq 200) {
            throw "PUBLIC_HTTP_200"
        }

        if ($status -eq 401 -or $status -eq 403) {
            return $true
        }

        if ($status -eq 302 -or $status -eq 303 -or $status -eq 307) {
            $location = $response.Headers.Location
            if ($null -eq $location) {
                throw "ACCESS_REDIRECT_WITHOUT_LOCATION"
            }

            $locationText = $location.AbsoluteUri
            if (
                $location.Host.EndsWith(
                    ".cloudflareaccess.com",
                    [System.StringComparison]::OrdinalIgnoreCase
                ) -or
                $locationText.Contains("/cdn-cgi/access/")
            ) {
                return $true
            }

            throw "UNEXPECTED_REDIRECT"
        }

        return $false
    }
    finally {
        $client.Dispose()
    }
}

if ($Stop) {
    Stop-ManagedTunnel
    exit 0
}

if ([string]::IsNullOrWhiteSpace($Hostname)) {
    Stop-WithReason "remote_hostname_missing"
}
$Hostname = $Hostname.Trim().ToLowerInvariant()
if ($Hostname -notmatch "^[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$" -or $Hostname -notmatch "\.") {
    Stop-WithReason "remote_hostname_invalid"
}

$TunnelToken = [Environment]::GetEnvironmentVariable(
    "JAP_DEMO_CLOUDFLARE_TUNNEL_TOKEN",
    [EnvironmentVariableTarget]::Process
)
if ([string]::IsNullOrWhiteSpace($TunnelToken)) {
    Stop-WithReason "tunnel_token_missing"
}

$existing = Get-ManagedTunnelProcess
if ($null -ne $existing) {
    Stop-WithReason "managed_tunnel_already_running"
}
Remove-Item -LiteralPath $StateFile -Force -ErrorAction SilentlyContinue

Assert-LocalJapReady

$cloudflaredPath = Get-CloudflaredPath
New-Item -ItemType Directory -Path $StateRoot -Force | Out-Null

$startInfo = New-Object System.Diagnostics.ProcessStartInfo
$startInfo.FileName = $cloudflaredPath
$startInfo.Arguments = "tunnel --no-autoupdate run"
$startInfo.UseShellExecute = $false
$startInfo.CreateNoWindow = $true
$startInfo.EnvironmentVariables["TUNNEL_TOKEN"] = $TunnelToken

$process = $null
$ready = $false
try {
    $process = [System.Diagnostics.Process]::Start($startInfo)
    if ($null -eq $process) {
        Stop-WithReason "cloudflared_start_failed"
    }

    $deadline = [DateTimeOffset]::UtcNow.AddSeconds($AccessProbeTimeoutSeconds)
    $lastProbe = "no_response"

    while ([DateTimeOffset]::UtcNow -lt $deadline) {
        if ($process.HasExited) {
            Stop-WithReason "cloudflared_exited_$($process.ExitCode)"
        }

        try {
            if (Test-AccessChallenge -RemoteHostname $Hostname) {
                $ready = $true
                break
            }
            $lastProbe = "route_not_ready"
        }
        catch {
            $lastProbe = $_.Exception.Message
            if ($lastProbe -eq "PUBLIC_HTTP_200") {
                Stop-WithReason "cloudflare_access_not_enforced"
            }
            if (
                $lastProbe -eq "ACCESS_REDIRECT_WITHOUT_LOCATION" -or
                $lastProbe -eq "UNEXPECTED_REDIRECT"
            ) {
                Stop-WithReason "cloudflare_access_unproven_$lastProbe"
            }
        }

        Start-Sleep -Milliseconds 750
    }

    if (-not $ready) {
        Stop-WithReason "access_probe_timeout_$lastProbe"
    }

    $state = [ordered]@{
        schema = "job_application_pipeline.classic_remote_demo_process.v1"
        pid = $process.Id
        cloudflared_path = $cloudflaredPath
        origin = $Origin
        remote_hostname = $Hostname
        started_at_utc = [DateTimeOffset]::UtcNow.ToString("o")
        access_gate = "unauthenticated_request_blocked_or_challenged"
    }
    $state | ConvertTo-Json | Set-Content -LiteralPath $StateFile -Encoding UTF8

    Write-Host "JAP_CLASSIC_REMOTE_DEMO=READY"
    Write-Host "JAP_CLASSIC_REMOTE_ORIGIN=$Origin"
    Write-Host "JAP_CLASSIC_REMOTE_URL=https://$Hostname/"
    Write-Host "JAP_CLASSIC_REMOTE_ACCESS=PROTECTED"
    Write-Host "JAP_CLASSIC_REMOTE_PID=$($process.Id)"
}
finally {
    if (-not $ready -and $null -ne $process -and -not $process.HasExited) {
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    }
}
