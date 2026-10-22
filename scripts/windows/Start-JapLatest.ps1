#requires -Version 7.1
[CmdletBinding()]
param([switch]$VerifyOnly)
$ErrorActionPreference='Stop'
function Read-Json($p){Get-Content -LiteralPath $p -Raw | ConvertFrom-Json}
function Resolve-Installation($root){
  $m=Read-Json (Join-Path $root 'current.json')
  $version=$m.desktop_host_version
  $b=Read-Json (Join-Path $root 'desktop-host/build-info.json')
  $r=Read-Json (Join-Path $root 'runtime/runtime-info.json')
  $f=Read-Json (Join-Path $root 'runtime/runtime-feature-contract.json')
  if($m.repository -ne 'jenshaberle-dotcom/job-application-pipeline' -or $m.compatibility_line -ne 'cgkb-product-local-1'){throw 'Incompatible installation'}
  foreach($item in @($b,$r,$f)){
    if($item.version -ne $version -or $item.source_sha -ne $m.pinned_sha){throw 'Installation identity mismatch'}
  }
  $runtime=[IO.Path]::GetFullPath((Join-Path $root 'runtime'))+[IO.Path]::DirectorySeparatorChar
  foreach($file in $f.critical_files.PSObject.Properties){
    $path=[IO.Path]::GetFullPath((Join-Path $runtime $file.Name))
    if(-not $path.StartsWith($runtime,[StringComparison]::OrdinalIgnoreCase)){throw 'Invalid contract path'}
    if((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -ne $file.Value){throw 'Runtime integrity mismatch'}
  }
  $exe=Join-Path $root 'desktop-host/JAP.ControlCenter.Desktop.exe'
  if(-not(Test-Path -LiteralPath $exe)){throw 'Desktop executable missing'}
  [pscustomobject]@{root=$root;exe=$exe;version=[version]$version;source=$m.pinned_sha}
}
$roots=@(Get-ChildItem -LiteralPath $env:LOCALAPPDATA -Directory | Where-Object {($_.Name -eq 'JAP-Control-Center' -or $_.Name -match '^JAP-Control-Center-Preview-[a-f0-9]+$') -and -not($_.Attributes -band [IO.FileAttributes]::ReparsePoint)})
$valid=@();$invalid=@()
foreach($root in $roots){try{$valid+=Resolve-Installation $root.FullName}catch{$invalid+=[pscustomobject]@{root=$root.FullName;reason=$_.Exception.Message}}}
$selected=$valid | Sort-Object version -Descending | Select-Object -First 1
if(-not $selected){throw 'Keine vollstaendige JAP-Installation gefunden.'}
$result=[ordered]@{status='LATEST_INSTALLED_VERSION_SELECTED';version=$selected.version.ToString();source=$selected.source;path=$selected.exe;rejected=$invalid}
if($VerifyOnly){$result | ConvertTo-Json -Depth 5;exit}
Add-Type -AssemblyName System.Windows.Forms
try{
  foreach($root in $roots){if(Test-Path -LiteralPath (Join-Path $root.FullName 'state/update-handoff.json')){throw 'Ein JAP-Update wird gerade uebergeben. Bitte nach dessen Abschluss erneut starten.'}}
  $running=@(Get-Process -Name 'JAP.ControlCenter.Desktop' -ErrorAction SilentlyContinue)
  $old=@($running | Where-Object {$_.Path -ne $selected.exe})
  if($old.Count){
    $answer=[Windows.Forms.MessageBox]::Show("JAP $($selected.version) ist installiert. Das bisherige JAP-Fenster schliessen und die aktuelle Version oeffnen? Laufende RCC-Auftraege bleiben bestehen.",'JAP aktualisieren',[Windows.Forms.MessageBoxButtons]::YesNo,[Windows.Forms.MessageBoxIcon]::Question)
    if($answer -ne [Windows.Forms.DialogResult]::Yes){exit}
    foreach($process in $old){if(-not $process.CloseMainWindow() -or -not $process.WaitForExit(30000)){throw 'JAP konnte nicht regulaer geschlossen werden. Bitte das Fenster selbst schliessen und erneut starten.'}}
  }
  Start-Process -FilePath $selected.exe -WorkingDirectory (Split-Path $selected.exe)
}catch{[Windows.Forms.MessageBox]::Show($_.Exception.Message,'JAP-Start nicht abgeschlossen') | Out-Null;exit 1}
