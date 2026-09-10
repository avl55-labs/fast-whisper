# Builds the per-machine MSI for Group Policy or Intune deployment.
#
# The application itself must be built first: packaging\build.ps1 produces
# dist\FastWhisper, which this package harvests.
#
# Requires WiX 5, installed as a dotnet tool:
#   dotnet tool install --global wix --version 5.0.2

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

# Read from the package rather than repeating it here: a hardcoded number sat at 0.1.0
# through two releases and would have shipped a 0.1.2 payload under the wrong name.
$match = Select-String -Path "$root\fastwhisper\__init__.py" -Pattern '__version__\s*=\s*"([^"]+)"'
if (-not $match) { throw "could not read __version__ from fastwhisper\__init__.py" }
$version = $match.Matches[0].Groups[1].Value

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
