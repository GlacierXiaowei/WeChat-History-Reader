param(
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$WheelDir = Join-Path $Root "vendor\wheels"
$Requirements = Join-Path $Root "requirements-runtime.txt"

New-Item -ItemType Directory -Force -Path $WheelDir | Out-Null
Get-ChildItem -LiteralPath $WheelDir -Filter "*.whl" -File -ErrorAction SilentlyContinue |
    Remove-Item -Force

foreach ($minor in 10..14) {
    & $Python -m pip download `
        --only-binary=:all: `
        --platform win_amd64 `
        --implementation cp `
        --python-version ("3." + $minor) `
        --dest $WheelDir `
        --requirement $Requirements
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to download compatible Windows x64 wheels for CPython 3.$minor."
    }
    $zstandardWheel = Get-ChildItem -LiteralPath $WheelDir -Filter "zstandard-*.whl" -File |
        Where-Object { $_.Name -match ("(?i)cp3" + $minor + "-") }
    if (-not $zstandardWheel) {
        throw "No zstandard wheel for CPython 3.$minor was downloaded."
    }
}

$wheels = Get-ChildItem -LiteralPath $WheelDir -Filter "*.whl" -File
if (-not ($wheels | Where-Object { $_.Name -match "(?i)^pycryptodome-.*-abi3-win_amd64\.whl$" })) {
    throw "No compatible pycryptodome Windows x64 abi3 wheel was downloaded."
}
Write-Host "Wheels staged in $WheelDir"
