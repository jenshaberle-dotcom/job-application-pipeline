param(
    [Parameter(Mandatory = $true)]
    [string]$ExpectedSha,
    [Parameter(Mandatory = $true)]
    [string]$ExpectedVersion
)

$ErrorActionPreference = "Stop"
$installRoot = [System.IO.Path]::GetFullPath(
    (Join-Path $env:LOCALAPPDATA "JAP-Control-Center"))
$currentPath = Join-Path $installRoot "current.json"
$exe = [System.IO.Path]::GetFullPath(
    (Join-Path $installRoot "desktop-host\JAP.ControlCenter.Desktop.exe"))
$lifecycleLog = Join-Path $installRoot "logs\desktop-host-lifecycle.log"

if (-not (Test-Path $currentPath)) {
    throw "Installed JAP identity is missing: $currentPath"
}
if (-not (Test-Path $exe)) {
    throw "Installed JAP desktop host is missing: $exe"
}

$current = Get-Content -Raw -Encoding UTF8 $currentPath | ConvertFrom-Json
if ([string]$current.pinned_sha -ne $ExpectedSha -or
    [string]$current.desktop_host_version -ne $ExpectedVersion) {
    Write-Output (
        "JAP_HEADLESS_DESKTOP_PROOF=SKIP installed={0}@{1} expected={2}@{3}" -f
        $current.desktop_host_version,
        $current.pinned_sha,
        $ExpectedVersion,
        $ExpectedSha)
    exit 0
}

$preexisting = @(
    Get-Process -Name "JAP.ControlCenter.Desktop" -ErrorAction SilentlyContinue |
        Where-Object { $_.SessionId -eq 0 }
)
if ($preexisting.Count -ne 0) {
    throw "Headless rejection proof requires zero pre-existing Session-0 JAP desktop processes."
}

$startedAt = [DateTimeOffset]::UtcNow
$process = Start-Process -FilePath $exe -WorkingDirectory (Split-Path -Parent $exe) -PassThru
$pidUnderTest = $process.Id

if (-not $process.WaitForExit(10000)) {
    try {
        Stop-Process -Id $pidUnderTest -Force -ErrorAction SilentlyContinue
    }
    catch {
        # The bounded failure below remains authoritative.
    }
    throw "Headless JAP desktop PID $pidUnderTest did not exit within 10 seconds."
}

Start-Sleep -Milliseconds 250
if (Get-Process -Id $pidUnderTest -ErrorAction SilentlyContinue) {
    throw "Headless JAP desktop PID $pidUnderTest remained after reported exit."
}

if (-not (Test-Path $lifecycleLog)) {
    throw "Headless rejection lifecycle log was not written: $lifecycleLog"
}

$needle = "noninteractive_start_rejected`tpid=$pidUnderTest"
$proofLine = Get-Content -Encoding UTF8 $lifecycleLog |
    Where-Object { $_ -like "*$needle*" } |
    Select-Object -Last 1
if ([string]::IsNullOrWhiteSpace($proofLine)) {
    throw "Headless rejection lifecycle evidence is missing for PID $pidUnderTest."
}

$timestampText = ($proofLine -split "`t", 2)[0]
$timestamp = [DateTimeOffset]::Parse($timestampText)
if ($timestamp -lt $startedAt.AddSeconds(-1)) {
    throw "Headless rejection lifecycle evidence predates this proof run."
}

Write-Output "JAP_HEADLESS_DESKTOP_PROOF=PASS pid=$pidUnderTest version=$ExpectedVersion sha=$ExpectedSha"
