param(
    [switch]$Clean
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$SpecPath = Join-Path $ProjectRoot "FrameBatch.spec"
$DistDir = Join-Path $ProjectRoot "dist"
$BuildDir = Join-Path $ProjectRoot "build"
$ReleaseDir = Join-Path $DistDir "FrameBatch"

# Read version from pyproject.toml
$PyProjectPath = Join-Path $ProjectRoot "pyproject.toml"
$Version = "0.1.0"
if (Test-Path $PyProjectPath) {
    $content = Get-Content $PyProjectPath -Raw
    if ($content -match 'version\s*=\s*"([^"]+)"') {
        $Version = $matches[1]
    }
}

$ZipName = "FrameBatch-v$Version-windows-x64.zip"
$ZipPath = Join-Path $DistDir $ZipName

Set-Location $ProjectRoot

if (-not (Test-Path $SpecPath)) {
    throw "Missing PyInstaller spec: $SpecPath"
}

if ($Clean) {
    if (Test-Path $BuildDir) {
        Remove-Item -LiteralPath $BuildDir -Recurse -Force
    }
    if (Test-Path $ReleaseDir) {
        Remove-Item -LiteralPath $ReleaseDir -Recurse -Force
    }
    if (Test-Path $ZipPath) {
        Remove-Item -LiteralPath $ZipPath -Force
    }
}

$pyInstallerCheck = & python -m PyInstaller --version 2>$null
if ($LASTEXITCODE -ne 0) {
    throw 'PyInstaller is not installed. Run: python -m pip install -e ".[build]"'
}

Write-Host "Using PyInstaller $pyInstallerCheck"
python -m PyInstaller --noconfirm $SpecPath

if (-not (Test-Path (Join-Path $ReleaseDir "FrameBatch.exe"))) {
    throw "Build finished, but FrameBatch.exe was not found in $ReleaseDir"
}

# Copy user-facing docs to release directory
$DocsSourceDir = Join-Path $ProjectRoot "docs"
$DocsReleaseDir = Join-Path $ReleaseDir "docs"
if (Test-Path $DocsSourceDir) {
    if (Test-Path $DocsReleaseDir) {
        Remove-Item -LiteralPath $DocsReleaseDir -Recurse -Force
    }
    New-Item -ItemType Directory -Path $DocsReleaseDir | Out-Null
    foreach ($DocName in @("RELEASE.md", "FFMPEG_NOTICE.md")) {
        $DocPath = Join-Path $DocsSourceDir $DocName
        if (Test-Path $DocPath) {
            Copy-Item -LiteralPath $DocPath -Destination $DocsReleaseDir -Force
        }
    }
    Write-Host "Copied docs to release folder."
}

# Remove old zip if exists
if (Test-Path $ZipPath) {
    Remove-Item -LiteralPath $ZipPath -Force
}

# Copy usage instructions to release directory
$UsageFile = Get-ChildItem -LiteralPath $PSScriptRoot -Filter "*.txt" -File | Select-Object -First 1
if ($UsageFile) {
    Copy-Item -LiteralPath $UsageFile.FullName -Destination $ReleaseDir -Force
    Write-Host "Copied usage instructions to release folder."
}

Write-Host "Creating distributable zip: $ZipName ..."
Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::CreateFromDirectory(
    $ReleaseDir,
    $ZipPath,
    [System.IO.Compression.CompressionLevel]::Optimal,
    $false
)

if (-not (Test-Path $ZipPath)) {
    throw "Failed to create zip archive."
}

$ZipSize = [math]::Round((Get-Item $ZipPath).Length / 1MB, 1)
Write-Host ""
Write-Host "=============================================================================="
Write-Host "  Build completed successfully!"
Write-Host ""
Write-Host "  Release folder : $ReleaseDir"
Write-Host "  Distributable  : $ZipPath ($ZipSize MB)"
Write-Host ""
Write-Host "  Usage:"
Write-Host "    1. Send $ZipName to users"
Write-Host "    2. Users extract and double-click FrameBatch.exe to run"
Write-Host "    3. Bundled FFmpeg is auto-detected, no extra config needed"
Write-Host "=============================================================================="
