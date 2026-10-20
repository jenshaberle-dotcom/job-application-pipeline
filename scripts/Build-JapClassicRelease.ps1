#requires -Version 7.1
[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidatePattern('^[0-9a-f]{40}$')][string]$SourceSha,
    [Parameter(Mandatory)][string]$BuildRoot,
    [Parameter(Mandatory)][string]$Python,
    [Parameter(Mandatory)][string]$LinuxPython,
    [string]$Distro = 'Ubuntu',
    [string]$LinuxUser = 'jens_h'
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$SourceRoot = Split-Path -Parent $PSScriptRoot
$BuildRoot = [IO.Path]::GetFullPath($BuildRoot)
if (Test-Path -LiteralPath $BuildRoot) { throw 'BUILD_ROOT_EXISTS_NO_OVERWRITE' }
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) { throw 'PYTHON_NOT_FOUND' }
if (-not $IsWindows) { throw 'WINDOWS_RELEASE_BUILD_REQUIRED' }
Push-Location $SourceRoot
try {
    if ((git rev-parse HEAD).Trim() -ne $SourceSha) { throw 'SOURCE_SHA_MISMATCH' }
    if (git status --porcelain --untracked-files=no) { throw 'TRACKED_SOURCE_DIRTY' }
    if ((& node -p "process.versions.node.split('.')[0]").Trim() -ne '22') { throw 'NODE22_REQUIRED' }
    if (-not ((& dotnet --list-sdks) -match '^8\.')) { throw 'DOTNET8_REQUIRED' }
    New-Item -ItemType Directory -Path $BuildRoot | Out-Null
Write-Host "Validate product and package contracts; no publication or installation"
$ErrorActionPreference = 'Stop'
& $Python -m pip check
if ($LASTEXITCODE -ne 0) { throw 'Python dependency validation failed' }
& $Python -X utf8 -m compileall -q src scripts tests
if ($LASTEXITCODE -ne 0) { throw 'Python compile validation failed' }
& $Python -X utf8 scripts/validate_ci_contract.py
if ($LASTEXITCODE -ne 0) { throw 'CI contract validation failed' }
& $Python -X utf8 scripts/check_documentation_references.py
if ($LASTEXITCODE -ne 0) { throw 'Documentation reference validation failed' }
& $Python -X utf8 scripts/check_documentation_architecture.py
if ($LASTEXITCODE -ne 0) { throw 'Documentation architecture validation failed' }
$ruff = Join-Path (Split-Path -Parent $Python) 'ruff.exe'
if (-not (Test-Path -LiteralPath $ruff)) { throw 'qualified Ruff executable missing' }
& $ruff check . --select E4,E7,E9,F --ignore E402
if ($LASTEXITCODE -ne 0) { throw 'Ruff validation failed' }
$LinuxSource = (& wsl.exe -d $Distro -u $LinuxUser --exec wslpath -a $SourceRoot).Trim()
if ($LASTEXITCODE -ne 0) { throw 'WSL source conversion failed' }
& wsl.exe -d $Distro -u $LinuxUser --cd $LinuxSource --exec $LinuxPython -m pytest -q
if ($LASTEXITCODE -ne 0) { throw 'Product regression tests failed' }
npm install --prefix frontend/control-center --no-audit --no-fund
if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency preparation failed' }
npm run build --prefix frontend/control-center
if ($LASTEXITCODE -ne 0) { throw 'Frontend validation build failed' }

Write-Host "Prove package-facing contracts on Windows"
& $Python -m py_compile scripts/product_v1_control_center_base.py scripts/run_product_v1_live_demo.py src/search_intelligence/product_v1_candidate_fit.py src/search_intelligence/product_v1_service.py
if ($LASTEXITCODE -ne 0) { throw 'Package compile validation failed' }
& $Python -X utf8 -m pytest -q tests/test_product_v1_candidate_fit.py tests/test_affinity_surface_consistency.py tests/test_release_payload_contract.py tests/test_product_v1_assessment_cohort_contract.py tests/test_demo_release_1_2_4_contract.py tests/test_google_connection.py
if ($LASTEXITCODE -ne 0) { throw 'Package regression tests failed' }

Write-Host "Resolve immutable product version"
$Version = (Get-Content "windows/JAP.ControlCenter.Desktop/VERSION" -Raw).Trim()
if ($Version -notmatch '^\d+\.\d+\.\d+$') {
  throw "Invalid JAP product VERSION: $Version"
}
if ([version]$Version -lt [version]"1.0.65") {
  throw "Supported CGKB product-local release baseline starts at 1.0.65."
}
$ProductVersion = $Version
$ProductTag = "jap-winapp-product-v$Version"

Write-Host "Prove CGKB product-local compatibility contract"
$Contract = Get-Content "windows/JAP.ControlCenter.Desktop/UPDATE_COMPATIBILITY.json" -Raw | ConvertFrom-Json
if ($Contract.schema -ne "job_application_pipeline.windows_update_compatibility.v2") {
  throw "Unexpected update compatibility schema: $($Contract.schema)"
}
if ($Contract.policy -ne "product_local_latest_direct") {
  throw "Product release policy must be product_local_latest_direct."
}
if ($Contract.compatibility_line -ne "cgkb-product-local-1") {
  throw "Unexpected product-local compatibility line."
}
if ($Contract.update_generation -ne "cgkb_product_local_v1") {
  throw "Unexpected product-local update generation."
}
if ($Contract.release_namespace -ne "jap-winapp-product-v") {
  throw "Unexpected product release namespace."
}
if ($Contract.installer_schema -ne "job_application_pipeline.windows_control_center_install.v3") {
  throw "Product release installer schema is incompatible."
}
if ([int]$Contract.snooze_hours -ne 6) {
  throw "GUI update snooze contract must remain 6 hours."
}
Write-Host "JAP_UPDATE_GENERATION=cgkb_product_local_v1"

Write-Host "Build source-bound React Control Center"
Push-Location frontend/control-center
npm install --no-audit --no-fund
if ($LASTEXITCODE -ne 0) { throw 'Frontend packaging dependency preparation failed' }
npm run build
if ($LASTEXITCODE -ne 0) { throw 'Frontend packaging build failed' }
Pop-Location
$Dist = "frontend/control-center/dist"
if (-not (Test-Path (Join-Path $Dist "index.html"))) {
  throw "React Control Center build did not produce dist/index.html."
}
Set-Content -Path (Join-Path $Dist ".jap-source-sha") -Value $SourceSha -Encoding ASCII -NoNewline

Write-Host "Publish self-contained Windows x64 host"
$Out = Join-Path $BuildRoot "jap-desktop-host"
dotnet publish windows/JAP.ControlCenter.Desktop/JAP.ControlCenter.Desktop.csproj `
  -c Release `
  -r win-x64 `
  --self-contained true `
  -o $Out
if ($LASTEXITCODE -ne 0) { throw 'Desktop publish failed' }
if (-not (Test-Path (Join-Path $Out "JAP.ControlCenter.Desktop.exe"))) {
  throw "Desktop host publish did not produce JAP.ControlCenter.Desktop.exe"
}
@{
  schema = "job_application_pipeline.desktop_host_build.v2"
  version = $ProductVersion
  repository_id = 1230805345
  repository = "jenshaberle-dotcom/job-application-pipeline"
  source_sha = $SourceSha
  runtime = "win-x64-self-contained"
  surface = "webview2-winforms"
  update_policy = "product_local_latest_direct"
  update_generation = "cgkb_product_local_v1"
  compatibility_line = "cgkb-product-local-1"
} | ConvertTo-Json | Set-Content -Encoding UTF8 (Join-Path $Out "build-info.json")

Write-Host "Assemble immutable WSL runtime bundle"
$Runtime = Join-Path $BuildRoot "jap-runtime"
New-Item -ItemType Directory -Force -Path $Runtime | Out-Null

# JAP 1.1.x embeds the official Codex CLI as a product runtime dependency.
# The binary is fetched only at release-build time, pinned to one official
# OpenAI release asset and checksum, then shipped inside the immutable
# runtime bundle. Installed startup never performs npm/curl/self-update.
$CodexVersion = "0.154.0"
$CodexArchiveName = "codex-x86_64-unknown-linux-musl.tar.gz"
$CodexArchiveSha256 = "d7e18b2597ae8f242f5f31ee9e90deef48dbc9edd634d9868fb6435d08c07f02"
$CodexReleaseUrl = "https://github.com/openai/codex/releases/download/rust-v$CodexVersion/$CodexArchiveName"
$CodexArchive = Join-Path $BuildRoot $CodexArchiveName
$CodexExtract = Join-Path $BuildRoot "jap-codex-linux-x64"
if (Test-Path -LiteralPath $CodexExtract) { throw "Fresh build directory required" }
if (Test-Path -LiteralPath $CodexArchive) { throw "Fresh archive path required" }
Invoke-WebRequest -UseBasicParsing -Uri $CodexReleaseUrl -OutFile $CodexArchive
$ActualArchiveSha256 = (Get-FileHash $CodexArchive -Algorithm SHA256).Hash.ToLowerInvariant()
if ($ActualArchiveSha256 -ne $CodexArchiveSha256) {
  throw "Official Codex archive checksum mismatch."
}
New-Item -ItemType Directory -Force -Path $CodexExtract | Out-Null
tar -xzf $CodexArchive -C $CodexExtract
if ($LASTEXITCODE -ne 0) {
  throw "Official Codex archive extraction failed."
}
$CodexBinary = @(
  Get-ChildItem -Path $CodexExtract -Recurse -File |
    Where-Object { $_.Name -eq "codex-x86_64-unknown-linux-musl" -or $_.Name -eq "codex" }
)
if ($CodexBinary.Count -ne 1) {
  throw "Expected exactly one official Codex Linux x64 binary, found $($CodexBinary.Count)."
}
$CodexVendor = Join-Path $Runtime "vendor\codex"
New-Item -ItemType Directory -Force -Path $CodexVendor | Out-Null
Copy-Item -Force $CodexBinary[0].FullName (Join-Path $CodexVendor "codex")
$CodexBinarySha256 = (Get-FileHash (Join-Path $CodexVendor "codex") -Algorithm SHA256).Hash.ToLowerInvariant()
@{
  schema = "job_application_pipeline.codex_runtime.v1"
  version = $CodexVersion
  platform = "x86_64-unknown-linux-musl"
  upstream_repository = "openai/codex"
  upstream_release = "rust-v$CodexVersion"
  archive_sha256 = $CodexArchiveSha256
  binary_sha256 = $CodexBinarySha256
  authentication = "chatgpt_cli_login"
  billing = "chatgpt_included_allowance_then_eligible_credits"
  auto_purchase = $false
  auto_api_key_fallback = $false
} | ConvertTo-Json | Set-Content -Encoding UTF8 (Join-Path $CodexVendor "codex-info.json")

foreach ($Directory in @("src", "scripts", "config", "contracts", "db")) {
  if (Test-Path $Directory) {
    Copy-Item -Recurse -Force $Directory (Join-Path $Runtime $Directory)
  }
}
foreach ($File in @("requirements.txt", "pyproject.toml", "VERSION")) {
  if (Test-Path $File) {
    Copy-Item -Force $File (Join-Path $Runtime $File)
  }
}
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$RuntimeShellScripts = @(Get-ChildItem -Path (Join-Path $Runtime "scripts") -Filter "*.sh" -File -Recurse)
if ($RuntimeShellScripts.Count -eq 0) {
  throw "Runtime bundle contains no shell scripts to normalize."
}
foreach ($ShellScript in $RuntimeShellScripts) {
  $Body = [System.IO.File]::ReadAllText($ShellScript.FullName)
  $Body = $Body.Replace("`r`n", "`n").Replace("`r", "`n")
  [System.IO.File]::WriteAllText($ShellScript.FullName, $Body, $Utf8NoBom)
  $Bytes = [System.IO.File]::ReadAllBytes($ShellScript.FullName)
  if ($Bytes -contains 13) {
    throw "Runtime shell script still contains CR bytes: $($ShellScript.FullName)"
  }
}
$DesktopMetadata = Join-Path $Runtime "windows\JAP.ControlCenter.Desktop"
New-Item -ItemType Directory -Force -Path $DesktopMetadata | Out-Null
Copy-Item -Force "windows\JAP.ControlCenter.Desktop\VERSION" (Join-Path $DesktopMetadata "VERSION")
Copy-Item -Force "windows\JAP.ControlCenter.Desktop\UPDATE_COMPATIBILITY.json" (Join-Path $DesktopMetadata "UPDATE_COMPATIBILITY.json")
$Frontend = Join-Path $Runtime "frontend\control-center\dist"
New-Item -ItemType Directory -Force -Path $Frontend | Out-Null
Get-ChildItem -Force "frontend\control-center\dist" | Copy-Item -Destination $Frontend -Recurse -Force
Set-Content -Path (Join-Path $Frontend ".jap-source-sha") -Value $SourceSha -Encoding ASCII -NoNewline
@{
  schema = "job_application_pipeline.runtime_bundle.v1"
  version = $ProductVersion
  repository_id = 1230805345
  repository = "jenshaberle-dotcom/job-application-pipeline"
  source_sha = $SourceSha
  update_policy = "product_local_latest_direct"
  update_generation = "cgkb_product_local_v1"
  compatibility_line = "cgkb-product-local-1"
  codex = @{
    version = $CodexVersion
    platform = "x86_64-unknown-linux-musl"
    binary_sha256 = $CodexBinarySha256
    auth_mode = "chatgpt_cli_login"
  }
} | ConvertTo-Json -Depth 4 | Set-Content -Encoding UTF8 (Join-Path $Runtime "runtime-info.json")

# PASS 1: prove the assembled runtime is an exact copy of the intended
# Candidate Fit/Affinity source and frontend build before ZIP creation.
$CriticalSourceFiles = @(
  "src/search_intelligence/product_v1_candidate_fit.py",
  "src/search_intelligence/product_v1_service.py",
  "scripts/product_v1_control_center_base.py",
  "scripts/run_product_v1_assessment_cohort.py",
  "scripts/product_v1_assessment_actions.py",
  "scripts/run_product_v1_live_demo.py",
  "scripts/run_jap_windows_control_center.sh"
)
foreach ($Relative in $CriticalSourceFiles) {
  $SourceHash = (Get-FileHash $Relative -Algorithm SHA256).Hash.ToLowerInvariant()
  $RuntimePath = Join-Path $Runtime $Relative
  if (-not (Test-Path $RuntimePath)) {
    throw "Runtime feature payload is missing $Relative"
  }
  $RuntimeFileHash = (Get-FileHash $RuntimePath -Algorithm SHA256).Hash.ToLowerInvariant()
  if ($SourceHash -ne $RuntimeFileHash) {
    throw "Runtime feature payload differs from checked-out source: $Relative"
  }
}

$SourceDist = (Resolve-Path "frontend/control-center/dist").Path
$RuntimeDist = (Resolve-Path $Frontend).Path
$SourceDistFiles = @(Get-ChildItem -Path $SourceDist -Recurse -File)
$RuntimeDistFiles = @(Get-ChildItem -Path $RuntimeDist -Recurse -File)
if ($SourceDistFiles.Count -ne $RuntimeDistFiles.Count) {
  throw "Runtime frontend file cardinality differs from built frontend."
}
foreach ($SourceFile in $SourceDistFiles) {
  $Relative = $SourceFile.FullName.Substring($SourceDist.Length).TrimStart("\", "/")
  $RuntimeFile = Join-Path $RuntimeDist $Relative
  if (-not (Test-Path $RuntimeFile)) {
    throw "Runtime frontend is missing built file: $Relative"
  }
  $SourceHash = (Get-FileHash $SourceFile.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
  $RuntimeFileHash = (Get-FileHash $RuntimeFile -Algorithm SHA256).Hash.ToLowerInvariant()
  if ($SourceHash -ne $RuntimeFileHash) {
    throw "Runtime frontend differs from built frontend: $Relative"
  }
}

$CriticalHashes = [ordered]@{}
foreach ($Relative in $CriticalSourceFiles) {
  $Normalized = $Relative.Replace("\", "/")
  $CriticalHashes[$Normalized] = (Get-FileHash (Join-Path $Runtime $Relative) -Algorithm SHA256).Hash.ToLowerInvariant()
}
foreach ($RuntimeFrontendFile in $RuntimeDistFiles) {
  $RelativeDist = $RuntimeFrontendFile.FullName.Substring($Runtime.Length).TrimStart("\", "/").Replace("\", "/")
  $CriticalHashes[$RelativeDist] = (Get-FileHash $RuntimeFrontendFile.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
}
$RuntimeFeatureContract = @{
  schema = "job_application_pipeline.runtime_feature_contract.v1"
  version = $ProductVersion
  source_sha = $SourceSha
  features = [ordered]@{
    candidate_fit_scope = "job_skills_vs_cv_skills"
    demo_cohort_policy = "frozen_runtime_identity"
    candidate_fit_required_count = 10
    affinity_required_count = 10
    combined_score_authority = $false
    static_cache_control = "no-store,max-age=0"
    frontend_generation_binding = "source_sha"
  }
  critical_files = $CriticalHashes
} | ConvertTo-Json -Depth 8
[System.IO.File]::WriteAllText(
  (Join-Path $Runtime "runtime-feature-contract.json"),
  $RuntimeFeatureContract,
  [System.Text.UTF8Encoding]::new($false)
)
Write-Host "JAP_RUNTIME_FEATURE_PAYLOAD_PASS1=PASS files=$($CriticalHashes.Count)"

foreach ($Required in @(
  "scripts\run_product_v1_live_demo.py",
  "scripts\run_product_v1_assessment_cohort.py",
  "scripts\product_v1_assessment_actions.py",
  "scripts\product_v1_control_center_base.py",
  "src\search_intelligence\product_v1_candidate_fit.py",
  "src\search_intelligence\product_v1_service.py",
  "runtime-feature-contract.json",
  "scripts\run_jap_windows_control_center.sh",
  "scripts\ensure_pinned_local_oss_runtime.sh",
  "vendor\codex\codex",
  "vendor\codex\codex-info.json",
  "requirements.txt",
  "frontend\control-center\dist\index.html",
  "frontend\control-center\dist\.jap-source-sha",
  "windows\JAP.ControlCenter.Desktop\VERSION",
  "windows\JAP.ControlCenter.Desktop\UPDATE_COMPATIBILITY.json",
  "runtime-info.json"
)) {
  if (-not (Test-Path (Join-Path $Runtime $Required))) {
    throw "Runtime bundle is missing $Required"
  }
}

Write-Host "Package product assets and checksums"
$DesktopOut = Join-Path $BuildRoot "jap-desktop-host"
$RuntimeOut = Join-Path $BuildRoot "jap-runtime"
$DesktopAsset = "JAP-Control-Center-Desktop-win-x64.zip"
$RuntimeAsset = "JAP-Control-Center-Runtime.zip"
foreach ($Asset in @($DesktopAsset, $RuntimeAsset, "$DesktopAsset.sha256", "$RuntimeAsset.sha256")) {
  if (Test-Path -LiteralPath (Join-Path $BuildRoot $Asset)) { throw "Asset already exists" }
}
Add-Type -AssemblyName System.IO.Compression.FileSystem
$DesktopAssetPath = Join-Path $BuildRoot $DesktopAsset
$RuntimeAssetPath = Join-Path $BuildRoot $RuntimeAsset
[System.IO.Compression.ZipFile]::CreateFromDirectory(
  $DesktopOut,
  $DesktopAssetPath,
  [System.IO.Compression.CompressionLevel]::Optimal,
  $false
)
[System.IO.Compression.ZipFile]::CreateFromDirectory(
  $RuntimeOut,
  $RuntimeAssetPath,
  [System.IO.Compression.CompressionLevel]::Optimal,
  $false
)
$RuntimeZip = [System.IO.Compression.ZipFile]::OpenRead($RuntimeAssetPath)
try {
  $EntryNames = @($RuntimeZip.Entries | ForEach-Object { $_.FullName.Replace("\", "/") })
  foreach ($RequiredEntry in @(
    "runtime-info.json",
    "runtime-feature-contract.json",
    "scripts/run_product_v1_live_demo.py",
    "scripts/run_product_v1_assessment_cohort.py",
    "scripts/product_v1_assessment_actions.py",
    "scripts/product_v1_control_center_base.py",
    "src/search_intelligence/product_v1_candidate_fit.py",
    "src/search_intelligence/product_v1_service.py",
    "vendor/codex/codex",
    "vendor/codex/codex-info.json",
    "frontend/control-center/dist/index.html",
    "frontend/control-center/dist/.jap-source-sha"
  )) {
    if ($EntryNames -notcontains $RequiredEntry) {
      throw "Runtime release ZIP is missing required entry: $RequiredEntry"
    }
  }
  # PASS 2: independently re-open the final ZIP and verify the feature
  # contract plus every contracted payload hash inside the actual release asset.
  $FeatureEntry = $RuntimeZip.GetEntry("runtime-feature-contract.json")
  if ($null -eq $FeatureEntry) {
    throw "Runtime release ZIP has no runtime feature contract."
  }
  $FeatureReader = [System.IO.StreamReader]::new($FeatureEntry.Open(), [System.Text.Encoding]::UTF8, $true)
  try {
    $FeatureContract = $FeatureReader.ReadToEnd() | ConvertFrom-Json
  }
  finally {
    $FeatureReader.Dispose()
  }
  if ($FeatureContract.schema -ne "job_application_pipeline.runtime_feature_contract.v1") {
    throw "Runtime release feature contract schema mismatch."
  }
  if ($FeatureContract.version -ne $ProductVersion -or $FeatureContract.source_sha -ne $SourceSha) {
    throw "Runtime release feature contract identity mismatch."
  }
  if ($FeatureContract.features.candidate_fit_scope -ne "job_skills_vs_cv_skills" -or
      $FeatureContract.features.demo_cohort_policy -ne "frozen_runtime_identity" -or
      [int]$FeatureContract.features.candidate_fit_required_count -ne 10 -or
      [int]$FeatureContract.features.affinity_required_count -ne 10 -or
      [bool]$FeatureContract.features.combined_score_authority -ne $false -or
      $FeatureContract.features.static_cache_control -ne "no-store,max-age=0" -or
      $FeatureContract.features.frontend_generation_binding -ne "source_sha") {
    throw "Runtime release feature contract semantics mismatch."
  }
  foreach ($Property in $FeatureContract.critical_files.PSObject.Properties) {
    $EntryName = $Property.Name.Replace("\", "/")
    $ExpectedHash = [string]$Property.Value
    $PayloadEntry = @(
      $RuntimeZip.Entries |
        Where-Object { $_.FullName.Replace("\", "/") -eq $EntryName } |
        Select-Object -First 1
    )[0]
    if ($null -eq $PayloadEntry) {
      throw "Runtime release ZIP is missing contracted payload: $EntryName"
    }
    $PayloadStream = $PayloadEntry.Open()
    $Sha = [System.Security.Cryptography.SHA256]::Create()
    try {
      $HashBytes = $Sha.ComputeHash($PayloadStream)
      $ActualHash = ([System.BitConverter]::ToString($HashBytes)).Replace("-", "").ToLowerInvariant()
    }
    finally {
      $Sha.Dispose()
      $PayloadStream.Dispose()
    }
    if ($ActualHash -ne $ExpectedHash.ToLowerInvariant()) {
      throw "Runtime release ZIP payload hash mismatch: $EntryName"
    }
  }
  Write-Host "JAP_RUNTIME_FEATURE_PAYLOAD_PASS2=PASS files=$($FeatureContract.critical_files.PSObject.Properties.Count)"

  $ShellEntries = @($RuntimeZip.Entries | Where-Object { $_.FullName.Replace("\", "/") -like "scripts/*.sh" })
  if ($ShellEntries.Count -eq 0) {
    throw "Runtime release ZIP contains no shell scripts."
  }
  foreach ($ShellEntry in $ShellEntries) {
    $Reader = [System.IO.StreamReader]::new($ShellEntry.Open(), [System.Text.Encoding]::UTF8, $true)
    try {
      $ShellBody = $Reader.ReadToEnd()
      if ($ShellBody.Contains("`r")) {
        throw "Runtime release ZIP contains CR bytes in $($ShellEntry.FullName)"
      }
    }
    finally {
      $Reader.Dispose()
    }
  }
}
finally {
  $RuntimeZip.Dispose()
}
$DesktopZip = [System.IO.Compression.ZipFile]::OpenRead($DesktopAssetPath)
try {
  $DesktopEntries = @($DesktopZip.Entries | ForEach-Object { $_.FullName.Replace("\", "/") })
  foreach ($RequiredDesktopEntry in @("JAP.ControlCenter.Desktop.exe", "build-info.json")) {
    if ($DesktopEntries -notcontains $RequiredDesktopEntry) {
      throw "Desktop release ZIP is missing required entry: $RequiredDesktopEntry"
    }
  }
  $BuildInfoEntry = $DesktopZip.GetEntry("build-info.json")
  $BuildInfoReader = [System.IO.StreamReader]::new($BuildInfoEntry.Open(), [System.Text.Encoding]::UTF8, $true)
  try {
    $BuildInfo = $BuildInfoReader.ReadToEnd() | ConvertFrom-Json
  }
  finally {
    $BuildInfoReader.Dispose()
  }
  if ($BuildInfo.source_sha -ne $SourceSha -or $BuildInfo.version -ne $ProductVersion) {
    throw "Desktop release ZIP build identity mismatch."
  }
}
finally {
  $DesktopZip.Dispose()
}
Write-Host "JAP_DESKTOP_PAYLOAD_PASS2=PASS"

$DesktopHash = (Get-FileHash $DesktopAssetPath -Algorithm SHA256).Hash.ToLowerInvariant()
$RuntimeHash = (Get-FileHash $RuntimeAssetPath -Algorithm SHA256).Hash.ToLowerInvariant()
"$DesktopHash  $DesktopAsset" | Set-Content -Encoding ASCII (Join-Path $BuildRoot "$DesktopAsset.sha256")
"$RuntimeHash  $RuntimeAsset" | Set-Content -Encoding ASCII (Join-Path $BuildRoot "$RuntimeAsset.sha256")
Write-Host "JAP_DESKTOP_SHA256=$DesktopHash"
Write-Host "JAP_RUNTIME_SHA256=$RuntimeHash"
    @{schema='jap.native_release_build.v1';status='PACKAGE_VERIFIED';source_sha=$SourceSha;
      version=$ProductVersion;tag=$ProductTag;published=$false;installed=$false;
      execution_authority='operator-local-build';rcc_execution_qualified=$false;
      artifacts=@($DesktopAsset,"$DesktopAsset.sha256",$RuntimeAsset,"$RuntimeAsset.sha256")
    } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $BuildRoot 'build-result.json') -Encoding utf8
} finally { Pop-Location }
