param(
    [switch]$CheckOnly
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$BuildRoot = Join-Path $Root "build"
$Stage = Join-Path $BuildRoot "package-staging\2.1.2"

New-Item -ItemType Directory -Force -Path $BuildRoot | Out-Null
$ResolvedBuild = (Resolve-Path $BuildRoot).Path.TrimEnd("\")
$ResolvedStage = [IO.Path]::GetFullPath($Stage).TrimEnd("\")
if (-not $ResolvedStage.StartsWith($ResolvedBuild + "\", [StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to stage outside the build directory: $ResolvedStage"
}
if (Test-Path -LiteralPath $Stage) {
    Remove-Item -LiteralPath $Stage -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $Stage | Out-Null

function Copy-ReleaseItem([string]$RelativePath) {
    $source = Join-Path $Root $RelativePath
    $destination = Join-Path $Stage $RelativePath
    if (-not (Test-Path -LiteralPath $source)) {
        throw "Missing release input: $RelativePath"
    }
    $parent = Split-Path -Parent $destination
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    Copy-Item -LiteralPath $source -Destination $destination -Recurse -Force
}

foreach ($item in @(
    ".codex-plugin",
    "plugin.json",
    "pyproject.toml",
    "requirements-runtime.txt",
    "README.md",
    "README.en.md",
    "CHANGELOG.md",
    "docs\releases",
    "assets",
    "skills",
    "wechat_history_reader",
    "vendor\wheels",
    "scripts\plugin_bootstrap.py",
    "scripts\plugin_bootstrap.cmd"
)) {
    Copy-ReleaseItem $item
}

foreach ($forbidden in @(
    ".mcp.json",
    "mcp.json",
    "server.py",
    "wechat_history_reader\mcp_server.py"
)) {
    $forbiddenPath = Join-Path $Stage $forbidden
    if (Test-Path -LiteralPath $forbiddenPath) {
        Remove-Item -LiteralPath $forbiddenPath -Recurse -Force
    }
}
Get-ChildItem -LiteralPath $Stage -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue |
    Sort-Object FullName -Descending |
    Remove-Item -Recurse -Force
Get-ChildItem -LiteralPath $Stage -Recurse -File -Filter "*.pyc" -ErrorAction SilentlyContinue |
    Remove-Item -Force

$manifest = Get-Content -Raw (Join-Path $Stage ".codex-plugin\plugin.json") | ConvertFrom-Json
if ($manifest.version -ne "2.1.2") {
    throw "Unexpected staged plugin version: $($manifest.version)"
}
if (($manifest.interface.capabilities -join ",") -ne "Skill") {
    throw "The staged plugin must expose only the Skill capability."
}
foreach ($assetField in @("composerIcon", "logo")) {
    $asset = [string]$manifest.interface.$assetField
    if ([string]::IsNullOrWhiteSpace($asset)) {
        throw "Missing required Codex display asset field: interface.$assetField"
    }
    $assetPath = Join-Path $Stage ($asset.Replace("/", "\"))
    if (-not (Test-Path -LiteralPath $assetPath -PathType Leaf)) {
        throw "Missing staged Codex display asset for interface.$assetField`: $asset"
    }
}
$wheelDir = Join-Path $Stage "vendor\wheels"
$wheels = Get-ChildItem -LiteralPath $wheelDir -Filter "*.whl" -File
if (-not ($wheels | Where-Object { $_.Name -match "(?i)^pycryptodome-.*-abi3-win_amd64\.whl$" })) {
    throw "Missing pycryptodome Windows x64 abi3 wheel."
}
foreach ($minor in 10..14) {
    if (-not ($wheels | Where-Object { $_.Name -match ("(?i)^zstandard-.*-cp3" + $minor + "-cp3" + $minor + "-win_amd64\.whl$") })) {
        throw "Missing zstandard wheel for CPython 3.$minor."
    }
}
$stagedFiles = Get-ChildItem -LiteralPath $Stage -Recurse -File
foreach ($file in $stagedFiles) {
    if ($file.Name -in @(".mcp.json", "mcp.json", "server.py", "mcp_server.py")) {
        throw "Forbidden MCP artifact staged: $($file.FullName)"
    }
}
if ((Get-Content -Raw (Join-Path $Stage "pyproject.toml")) -match "(?im)^\s*['""]mcp") {
    throw "The staged project still declares an MCP dependency."
}

if (-not $CheckOnly) {
    $Dist = Join-Path $Root "dist"
    New-Item -ItemType Directory -Force -Path $Dist | Out-Null
    $Archive = Join-Path $Dist "wechat-history-reader-2.1.2.zip"
    if (Test-Path -LiteralPath $Archive) {
        Remove-Item -LiteralPath $Archive -Force
    }
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip = [IO.Compression.ZipFile]::Open($Archive, [IO.Compression.ZipArchiveMode]::Create)
    $archiveRoot = [string]$manifest.name
    try {
        foreach ($file in (Get-ChildItem -LiteralPath $Stage -Force -Recurse -File | Sort-Object FullName)) {
            $relativePath = ($archiveRoot + "/" + $file.FullName.Substring($Stage.Length + 1)).Replace("\", "/")
            [IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
                $zip, $file.FullName, $relativePath, [IO.Compression.CompressionLevel]::Optimal
            ) | Out-Null
        }
    } finally {
        $zip.Dispose()
    }
    Write-Host "Created $Archive"
}
Write-Host "Validated $Stage"
