# Builds the per-machine MSI for Group Policy or Intune deployment.
#
# The application itself must be built first: packaging\build.ps1 produces
# dist\FastWhisper, which this package harvests.
#
# Requires WiX 5, installed as a dotnet tool:
#   dotnet tool install --global wix --version 5.0.2

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$version = "0.1.0"

if (-not (Test-Path "$root\dist\FastWhisper\FastWhisper.exe")) {
    throw "dist\FastWhisper is missing - run packaging\build.ps1 first."
}

$wix = Get-Command wix -ErrorAction SilentlyContinue
if (-not $wix) {
    $candidate = "$env:USERPROFILE\.dotnet\tools\wix.exe"
    if (Test-Path $candidate) { $wix = $candidate } else { throw "wix not found. Install it with: dotnet tool install --global wix --version 5.0.2" }
} else {
    $wix = $wix.Source
}

& $wix build "$root\packaging\FastWhisper.wxs" -arch x64 -out "$root\dist\FastWhisper-$version.msi"
if ($LASTEXITCODE -ne 0) { throw "wix build failed" }

Write-Host "Built dist\FastWhisper-$version.msi"
