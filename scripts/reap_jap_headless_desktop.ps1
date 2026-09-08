$ErrorActionPreference = "Stop"

$expectedPath = [System.IO.Path]::GetFullPath(
    (Join-Path $env:LOCALAPPDATA "JAP-Control-Center\desktop-host\JAP.ControlCenter.Desktop.exe"))
$hosts = @(Get-Process -Name "JAP.ControlCenter.Desktop" -ErrorAction SilentlyContinue)

foreach ($hostProcess in $hosts) {
    if ($hostProcess.SessionId -ne 0) {
        continue
    }

    $actualPath = $null
    try {
        $actualPath = [System.IO.Path]::GetFullPath($hostProcess.Path)
    }
    catch {
        throw "Cannot prove executable identity for Session-0 JAP desktop PID $($hostProcess.Id)."
    }

    if (-not [string]::Equals(
            $actualPath,
            $expectedPath,
            [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to reap unexpected Session-0 process path for PID $($hostProcess.Id): $actualPath"
    }

    $pidToReap = $hostProcess.Id
    Stop-Process -Id $pidToReap -Force -ErrorAction Stop
    try {
        $hostProcess.WaitForExit(5000)
    }
    catch {
        # Re-probe below is authoritative.
    }

    if (Get-Process -Id $pidToReap -ErrorAction SilentlyContinue) {
        throw "Session-0 JAP desktop PID $pidToReap did not exit after bounded reap."
    }

    Write-Output "JAP_HEADLESS_DESKTOP_REAP=PASS pid=$pidToReap path=$actualPath"
}

Write-Output "JAP_HEADLESS_DESKTOP_REAP=COMPLETE"
