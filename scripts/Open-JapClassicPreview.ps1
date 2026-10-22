#requires -Version 7.1
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$PackageRoot,
    [Parameter(Mandatory)][ValidatePattern('^[0-9a-f]{40}$')][string]$SourceSha,
    [switch]$VerifyOnly
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
function Require($Condition, [string]$Reason) { if (-not $Condition) { throw $Reason } }
$PackageRoot = [IO.Path]::GetFullPath($PackageRoot)
$Result = Get-Content -LiteralPath (Join-Path $PackageRoot 'build-result.json') -Raw | ConvertFrom-Json
Require ($Result.status -eq 'PACKAGE_VERIFIED' -and $Result.source_sha -eq $SourceSha) 'BUILD_IDENTITY_MISMATCH'
$Assets = @('JAP-Control-Center-Desktop-win-x64.zip', 'JAP-Control-Center-Runtime.zip')
foreach ($Asset in $Assets) {
    $Hash = ((Get-Content -LiteralPath (Join-Path $PackageRoot "$Asset.sha256") -Raw).Trim() -split '\s+')[0]
    Require ($Hash -match '^[0-9a-f]{64}$') 'CHECKSUM_FORMAT'
    Require ((Get-FileHash -LiteralPath (Join-Path $PackageRoot $Asset) -Algorithm SHA256).Hash.ToLowerInvariant() -eq $Hash) 'CHECKSUM_MISMATCH'
}
if ($VerifyOnly) { Write-Host 'JAP_PREVIEW_ARCHIVES_VERIFIED_NO_INSTALLATION'; return }

$InstalledRoot = Join-Path $env:LOCALAPPDATA 'JAP-Control-Center'
$Current = Get-Content -LiteralPath (Join-Path $InstalledRoot 'current.json') -Raw | ConvertFrom-Json -AsHashtable
Require ($Current.repository_id -eq 1230805345 -and $Current.port -eq 8780) 'INSTALLED_IDENTITY_UNEXPECTED'
$PreviewRoot = Join-Path $env:LOCALAPPDATA ("JAP-Control-Center-Preview-" + $SourceSha.Substring(0,12))
Require (-not (Test-Path -LiteralPath $PreviewRoot)) 'PREVIEW_EXISTS_NO_OVERWRITE'
for ($Directory = [IO.DirectoryInfo]::new($PreviewRoot); $null -ne $Directory; $Directory = $Directory.Parent) {
    Require (-not ($Directory.Exists -and ($Directory.Attributes -band [IO.FileAttributes]::ReparsePoint))) 'LINKED_PREVIEW_PATH'
}

Add-Type -AssemblyName System.Windows.Forms
$Consent = [Windows.Forms.MessageBox]::Show(
    'JAP-Testversion vorbereiten und öffnen? Ein geöffnetes JAP-Fenster wird geordnet geschlossen. Die Testversion verwendet dieselbe Datenbank und Postfachanbindung. Die Installation 1.2.6 bleibt erhalten; RCC-Dienste werden nicht verändert.',
    'JAP Classic – Testversion', 'YesNo', 'Question')
if ($Consent -ne [Windows.Forms.DialogResult]::Yes) { return }
foreach ($Process in @(Get-Process -Name 'JAP.ControlCenter.Desktop' -ErrorAction SilentlyContinue)) {
    $Executable = $Process.Path
    Require ($Executable -and $Executable.StartsWith($InstalledRoot + '\', [StringComparison]::OrdinalIgnoreCase)) 'OTHER_JAP_INSTANCE_RUNNING'
    Require ($Process.CloseMainWindow()) 'JAP_WINDOW_CLOSE_FAILED'
    Require ($Process.WaitForExit(30000)) 'JAP_WINDOW_STILL_CLOSING_NO_FORCE'
}
$Listener = @(Get-NetTCPConnection -LocalPort 8780 -State Listen -ErrorAction SilentlyContinue)
Require ($Listener.Count -eq 0) 'JAP_RUNTIME_STILL_RUNNING_NO_SECOND_SERVER'

New-Item -ItemType Directory -Path $PreviewRoot | Out-Null
for ($Index=0; $Index -lt 2; $Index++) {
    $Target = Join-Path $PreviewRoot @('desktop-host','runtime')[$Index]
    $Zip = [IO.Compression.ZipFile]::OpenRead((Join-Path $PackageRoot $Assets[$Index]))
    try {
        foreach ($Entry in $Zip.Entries) {
            $Destination = [IO.Path]::GetFullPath((Join-Path $Target $Entry.FullName))
            Require ($Destination.StartsWith($Target + '\', [StringComparison]::OrdinalIgnoreCase)) 'ARCHIVE_PATH_ESCAPE'
            Require ((($Entry.ExternalAttributes -shr 16) -band 61440) -ne 40960) 'ARCHIVE_SYMLINK'
        }
    } finally { $Zip.Dispose() }
    [IO.Compression.ZipFile]::ExtractToDirectory((Join-Path $PackageRoot $Assets[$Index]), $Target)
}
$DesktopInfo = Get-Content -LiteralPath (Join-Path $PreviewRoot 'desktop-host/build-info.json') -Raw | ConvertFrom-Json
$RuntimeInfo = Get-Content -LiteralPath (Join-Path $PreviewRoot 'runtime/runtime-info.json') -Raw | ConvertFrom-Json
foreach ($Info in @($DesktopInfo,$RuntimeInfo)) {
    Require ($Info.source_sha -eq $SourceSha -and $Info.version -eq $Result.version -and $Info.repository_id -eq 1230805345) 'PAYLOAD_IDENTITY_MISMATCH'
    Require ($Info.compatibility_line -eq 'cgkb-product-local-1' -and $Info.update_generation -eq 'cgkb_product_local_v1') 'PAYLOAD_COMPATIBILITY_MISMATCH'
}
$Contract = Get-Content -LiteralPath (Join-Path $PreviewRoot 'runtime/runtime-feature-contract.json') -Raw | ConvertFrom-Json -AsHashtable
Require ($Contract.source_sha -eq $SourceSha -and $Contract.version -eq $Result.version) 'FEATURE_IDENTITY_MISMATCH'
foreach ($Entry in $Contract.critical_files.GetEnumerator()) {
    $Path = [IO.Path]::GetFullPath((Join-Path $PreviewRoot ('runtime/' + $Entry.Key)))
    Require ($Path.StartsWith((Join-Path $PreviewRoot 'runtime') + '\',[StringComparison]::OrdinalIgnoreCase)) 'FEATURE_PATH_ESCAPE'
    Require ((Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant() -eq $Entry.Value) 'FEATURE_HASH_MISMATCH'
}
$WslRoot = (& wsl.exe -d $Current.wsl_distro --exec wslpath -a -u $PreviewRoot).Trim()
Require ($LASTEXITCODE -eq 0 -and $WslRoot.StartsWith('/')) 'WSL_PATH_FAILED'
$Current.pinned_sha = $SourceSha
$Current.desktop_host_version = $Result.version
$Current.desktop_host_release = 'operator-preview-' + $Result.version
$Current.wsl_runtime_root = "$WslRoot/runtime"
$Current.wsl_runtime_runner_path = "$WslRoot/runtime/scripts/run_jap_windows_control_center.sh"
$Current.wsl_state_root += '-preview-' + $SourceSha.Substring(0,12)
$Current.desktop_host_sha256 = (Get-FileHash -LiteralPath (Join-Path $PackageRoot $Assets[0])).Hash.ToLowerInvariant()
$Current.runtime_bundle_sha256 = (Get-FileHash -LiteralPath (Join-Path $PackageRoot $Assets[1])).Hash.ToLowerInvariant()
$Current.Remove('desktop_host_tree_sha256')
$Current.Remove('runtime_tree_sha256')
$Current.operator_preview = $true
$Current.installed_at = [DateTime]::UtcNow.ToString('o')
$Current | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $PreviewRoot 'current.json') -Encoding utf8
Start-Process -FilePath (Join-Path $PreviewRoot 'desktop-host/JAP.ControlCenter.Desktop.exe')
Write-Host "JAP_PREVIEW_OPENED: $PreviewRoot"
Write-Host 'Zum Zurueckwechseln Testversion schliessen und JAP ueber die bisherige Verknuepfung oeffnen.'
