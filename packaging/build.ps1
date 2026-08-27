# Builds FastWhisper.exe and the installer.
# Usage:  powershell -ExecutionPolicy Bypass -File packaging\build.ps1
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$python = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) {
    Write-Host 'Creating the virtual environment...'
    py -3 -m venv .venv
    & $python -m pip install --upgrade pip
    & $python -m pip install -r requirements.txt pyinstaller
}

Write-Host 'Building the executable...'
& $python -m PyInstaller packaging\FastWhisper.spec --noconfirm --distpath dist --workpath build
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed' }

$iscc = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1

if ($iscc) {
    Write-Host 'Building the installer...'
    & $iscc packaging\installer.iss
    if ($LASTEXITCODE -ne 0) { throw 'Inno Setup failed' }
    Write-Host "Done: dist\FastWhisper-0.1.0-setup.exe"
} else {
    Write-Warning 'Inno Setup 6 not found, skipping the installer. Install it with: winget install JRSoftware.InnoSetup'
    Write-Host "Done: dist\FastWhisper\FastWhisper.exe"
}
