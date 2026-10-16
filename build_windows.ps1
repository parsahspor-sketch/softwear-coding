$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

$python = Join-Path $PSScriptRoot ".EpicVenv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    $pythonCommand = Get-Command python.exe -ErrorAction Stop
    $python = $pythonCommand.Source
}

& $python -m pip install -r (Join-Path $PSScriptRoot "requirements-build.txt")
if ($LASTEXITCODE -ne 0) {
    throw "Installing build requirements failed."
}

& $python (Join-Path $PSScriptRoot "make_icon.py")
if ($LASTEXITCODE -ne 0) {
    throw "Icon generation failed."
}

$release = Join-Path $PSScriptRoot "release"
New-Item -ItemType Directory -Force -Path $release | Out-Null

& $python -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name QuietHoursMonitor `
    --distpath $release `
    --workpath (Join-Path $PSScriptRoot "build\pyinstaller") `
    --specpath (Join-Path $PSScriptRoot "build") `
    --icon (Join-Path $PSScriptRoot "QuietHoursMonitor.ico") `
    --add-data "$(Join-Path $PSScriptRoot 'QuietHoursMonitor.ico');." `
    --add-data "$(Join-Path $PSScriptRoot 'QuietHoursLogoTransparent.png');." `
    --version-file (Join-Path $PSScriptRoot "version_info.txt") `
    --collect-all customtkinter `
    (Join-Path $PSScriptRoot "Main.py")
if ($LASTEXITCODE -ne 0) {
    throw "Building the standalone application failed."
}

$compilerPath = $null
$compilerCommand = Get-Command ISCC.exe -ErrorAction SilentlyContinue
if ($null -ne $compilerCommand) {
    $compilerPath = $compilerCommand.Source
}

if (-not $compilerPath) {
    $compilerPaths = @(
        "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 7\ISCC.exe"
    )
    foreach ($candidate in $compilerPaths) {
        if (Test-Path -LiteralPath $candidate) {
            $compilerPath = $candidate
            break
        }
    }
}

if ($compilerPath) {
    & $compilerPath (Join-Path $PSScriptRoot "QuietHoursMonitor.iss")
    if ($LASTEXITCODE -ne 0) {
        throw "Building the installer failed."
    }
    Write-Output "Installer: $(Join-Path $release 'QuietHoursMonitor-Setup.exe')"
} else {
    Write-Warning "Inno Setup is not installed. The standalone EXE is ready; install Inno Setup and rerun this script to create the setup EXE."
}

Write-Output "Standalone application: $(Join-Path $release 'QuietHoursMonitor.exe')"
