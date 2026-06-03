# build_release.ps1
# AdopyHzEditor one-folder PyInstaller build script.
#
# Usage:
#   .\scripts\build_release.ps1
#   .\scripts\build_release.ps1 -Clean
#   .\scripts\build_release.ps1 -NoZip
#   .\scripts\build_release.ps1 -Version 0.1.1
#
# Output:
#   dist\AdopyHzEditor\AdopyHzEditor.exe
#   releases\AdopyHzEditor_Windows_vX.Y.Z.zip  (unless -NoZip is used)

param(
    [switch]$Clean,
    [switch]$NoZip,
    [switch]$SkipInstall,
    [string]$Version = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Step([string]$Message) {
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Write-Ok([string]$Message) {
    Write-Host "OK: $Message" -ForegroundColor Green
}

function Fail([string]$Message) {
    Write-Host "ERROR: $Message" -ForegroundColor Red
    exit 1
}

function Get-RepoRoot {
    $scriptDir = Split-Path -Parent $PSCommandPath

    # If this script is in scripts\, repo root is parent.
    if ((Split-Path -Leaf $scriptDir) -ieq "scripts") {
        return (Resolve-Path (Join-Path $scriptDir "..")).Path
    }

    return (Resolve-Path $scriptDir).Path
}

function Invoke-CommandChecked {
    param(
        [Parameter(Mandatory=$true)][string]$FilePath,
        [Parameter(ValueFromRemainingArguments=$true)][string[]]$Arguments
    )

    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        Fail "Command failed: $FilePath $($Arguments -join ' ')"
    }
}

function Ensure-VenvPython([string]$Root) {
    $venvPython = Join-Path $Root ".venv\Scripts\python.exe"

    if (Test-Path $venvPython) {
        return $venvPython
    }

    Write-Step "Creating .venv"

    $created = $false

    try {
        & py -3.13 -m venv (Join-Path $Root ".venv")
        if ($LASTEXITCODE -eq 0) { $created = $true }
    } catch {
        $created = $false
    }

    if (-not $created) {
        try {
            & py -3.12 -m venv (Join-Path $Root ".venv")
            if ($LASTEXITCODE -eq 0) { $created = $true }
        } catch {
            $created = $false
        }
    }

    if (-not $created) {
        try {
            & python -m venv (Join-Path $Root ".venv")
            if ($LASTEXITCODE -eq 0) { $created = $true }
        } catch {
            $created = $false
        }
    }

    if (-not $created -or -not (Test-Path $venvPython)) {
        Fail "Failed to create .venv. Install Python 3.12+ or run this inside an existing project environment."
    }

    return $venvPython
}

function Ensure-BuildDeps([string]$Python, [string]$Root) {
    if ($SkipInstall) {
        Write-Step "Skipping dependency check/install"
        return
    }

    Write-Step "Checking build dependencies"

    & $Python -c "import PyInstaller" 2>$null
    $hasPyInstaller = ($LASTEXITCODE -eq 0)

    if (-not $hasPyInstaller) {
        Write-Step "Installing requirements and PyInstaller"
        Invoke-CommandChecked $Python -m pip install -U pip
        $req = Join-Path $Root "requirements.txt"
        if (Test-Path $req) {
            Invoke-CommandChecked $Python -m pip install -r $req
        }
        Invoke-CommandChecked $Python -m pip install pyinstaller
    } else {
        Write-Ok "PyInstaller is installed"
    }
}

function Read-AppVersion([string]$Root) {
    $appInfo = Join-Path $Root "app_info.py"

    if (-not (Test-Path $appInfo)) {
        return "dev"
    }

    $text = Get-Content $appInfo -Raw -Encoding UTF8
    if ($text -match 'APP_VERSION\s*=\s*["'']([^"'']+)["'']') {
        return $Matches[1]
    }

    return "dev"
}

$Root = Get-RepoRoot
Set-Location $Root

Write-Step "AdopyHzEditor build"
Write-Host "Root: $Root"

foreach ($required in @("main.py", "audio_analysis.py", "audio_player.py", "editor_view.py", "export_adofai.py", "requirements.txt", "locales")) {
    if (-not (Test-Path (Join-Path $Root $required))) {
        Fail "Required file/folder not found: $required"
    }
}

$Python = Ensure-VenvPython $Root
Write-Host "Python: $Python"

Ensure-BuildDeps $Python $Root

if ([string]::IsNullOrWhiteSpace($Version)) {
    $Version = Read-AppVersion $Root
}

$VersionTag = $Version
if (-not $VersionTag.StartsWith("v")) {
    $VersionTag = "v$VersionTag"
}

Write-Host "Version: $VersionTag"

if ($Clean) {
    Write-Step "Cleaning build/dist"
    Remove-Item -Recurse -Force (Join-Path $Root "build") -ErrorAction SilentlyContinue
    Remove-Item -Recurse -Force (Join-Path $Root "dist") -ErrorAction SilentlyContinue
}

Write-Step "Running PyInstaller"

# Do NOT use --collect-all PySide6 here.
# This app uses QtWidgets, not QML/QtQuick, and collecting all PySide6 can pull broken/unneeded QML plugins.
$pyiArgs = @(
    "main.py",
    "--name", "AdopyHzEditor",
    "--windowed",
    "--noconfirm",
    "--add-data", "locales;locales",

    "--hidden-import", "PySide6.QtCore",
    "--hidden-import", "PySide6.QtGui",
    "--hidden-import", "PySide6.QtWidgets",

    "--exclude-module", "PySide6.QtQml",
    "--exclude-module", "PySide6.QtQuick",
    "--exclude-module", "PySide6.QtQuickWidgets",
    "--exclude-module", "PySide6.QtQuickControls2",
    "--exclude-module", "PySide6.QtWebEngineCore",
    "--exclude-module", "PySide6.QtWebEngineWidgets",

    "--collect-all", "pyqtgraph",
    "--collect-all", "librosa",
    "--collect-all", "soundfile",
    "--collect-all", "sounddevice",
    "--collect-all", "audioread",
    "--collect-all", "mido"
)

if ($Clean) {
    $pyiArgs += "--clean"
}

Invoke-CommandChecked $Python -m PyInstaller @pyiArgs

$DistApp = Join-Path $Root "dist\AdopyHzEditor"
$Exe = Join-Path $DistApp "AdopyHzEditor.exe"

if (-not (Test-Path $Exe)) {
    Fail "Build finished but exe was not found: $Exe"
}

Write-Ok "Exe built: $Exe"

# Make locale placement robust.
# PyInstaller usually places add-data under _internal\locales in one-folder mode.
# i18n.py can also find locales next to the exe, so copy both places.
Write-Step "Ensuring locale files are bundled"

$InternalLocales = Join-Path $DistApp "_internal\locales"
$TopLocales = Join-Path $DistApp "locales"

New-Item -ItemType Directory -Force -Path $InternalLocales | Out-Null
New-Item -ItemType Directory -Force -Path $TopLocales | Out-Null

Copy-Item -Recurse -Force (Join-Path $Root "locales\*") $InternalLocales
Copy-Item -Recurse -Force (Join-Path $Root "locales\*") $TopLocales

if (-not (Test-Path (Join-Path $InternalLocales "en.json"))) {
    Fail "locales/en.json was not copied into _internal/locales"
}
if (-not (Test-Path (Join-Path $InternalLocales "ja.json"))) {
    Fail "locales/ja.json was not copied into _internal/locales"
}

Write-Ok "Locales copied"

if (-not $NoZip) {
    Write-Step "Creating release zip"

    $ReleaseDir = Join-Path $Root "releases"
    New-Item -ItemType Directory -Force -Path $ReleaseDir | Out-Null

    $ZipPath = Join-Path $ReleaseDir "AdopyHzEditor_Windows_$VersionTag.zip"
    Remove-Item -Force $ZipPath -ErrorAction SilentlyContinue

    # Zip the folder itself so users get:
    #   AdopyHzEditor\AdopyHzEditor.exe
    #   AdopyHzEditor\_internal\...
    Compress-Archive -Path $DistApp -DestinationPath $ZipPath -Force

    Write-Ok "Release zip: $ZipPath"
}

Write-Step "Done"

Write-Host ""
Write-Host "Run:"
Write-Host "  $Exe"
Write-Host ""
Write-Host "Release asset should usually be:"
Write-Host "  releases\AdopyHzEditor_Windows_$VersionTag.zip"
