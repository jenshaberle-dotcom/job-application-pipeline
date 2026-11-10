param(
    [Parameter(Mandatory)][string]$ContextFile,
    [Parameter(Mandatory)][string]$Repository,
    [Parameter(Mandatory)][string]$Runner,
    [Parameter(Mandatory)][string]$SourceSha
)
$ErrorActionPreference = 'Stop'
$context = Get-Content -LiteralPath $ContextFile -Raw | ConvertFrom-Json
if ($SourceSha -notmatch '^[0-9a-f]{40}$' -or
    [int64]$context.RepositoryId -ne 1230805345 -or
    [string]$context.Repository -ne $Repository -or
    [string]$context.RunnerName -ne $Runner -or
    [string]$context.SourceSha -ne $SourceSha -or
    [string]$context.Platform -ne 'windows' -or
    [string]$context.Status -ne 'PASS' -or
    $context.PrimaryFailure -or
    [string]$context.ProfileHash -notmatch '^[0-9a-f]{64}$' -or
    -not $context.ProfileId) { throw 'RCC Windows runtime identity or qualification mismatch' }

$paths = @($context.ToolPaths)
if ($paths.Count -eq 0) { throw 'RCC prepackaged tool paths missing' }
foreach ($path in $paths) {
    if ($path -isnot [string] -or $path -match '[\r\n\x00]' -or
        -not [IO.Path]::IsPathFullyQualified($path) -or
        -not (Test-Path -LiteralPath $path -PathType Container)) { throw 'Invalid RCC tool path' }
}
$tools = @{}
foreach ($entry in @(@('node', 'node-22', '^22\.'), @('dotnet', 'dotnet-sdk-8', '^8\.'))) {
    $name, $capability, $major = $entry
    $candidates = @($paths | ForEach-Object { Join-Path $_ "$name.exe" } |
        Where-Object { Test-Path -LiteralPath $_ -PathType Leaf })
    if ($candidates.Count -ne 1) { throw "RCC qualified $name missing or ambiguous" }
    $expected = [string]$context.ToolVersions.$capability
    if ($expected -notmatch $major) { throw "RCC qualified $name version missing" }
    $version = (& $candidates[0] --version).Trim().TrimStart('v')
    if ($LASTEXITCODE -ne 0 -or $version -ne $expected) { throw "RCC qualified $name version drift" }
    $tools[$name] = $candidates[0]
}
$python = [string]$context.Interpreter
if (-not [IO.Path]::IsPathFullyQualified($python) -or $python -match '[\r\n\x00]' -or
    -not (Test-Path -LiteralPath $python -PathType Leaf)) { throw 'RCC qualified Python missing' }
foreach ($path in $paths) { $path >> $env:GITHUB_PATH }
$env:PATH = ($paths -join [IO.Path]::PathSeparator) + [IO.Path]::PathSeparator + $env:PATH
$env:DOTNET_ROOT = Split-Path -Parent $tools.dotnet
"DOTNET_ROOT=$env:DOTNET_ROOT" >> $env:GITHUB_ENV
$python
