# build_release.ps1
# Build the current React + pywebview UI as a Windows one-folder release.
#
# Usage:
#   .\scripts\build_release.ps1
#   .\scripts\build_release.ps1 -Clean
#   .\scripts\build_release.ps1 -NoZip
#   .\scripts\build_release.ps1 -Version 0.8.0
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

function Get-RepoRoot {
    $scriptDir = Split-Path -Parent $PSCommandPath
    if ((Split-Path -Leaf $scriptDir) -ieq "scripts") {
        return (Resolve-Path (Join-Path $scriptDir "..")).Path
    }
    return (Resolve-Path $scriptDir).Path
}

function Find-CommandPath([string[]]$Names) {
    foreach ($name in $Names) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($null -ne $cmd) {
            if ($cmd.Source) { return $cmd.Source }
            if ($cmd.Path) { return $cmd.Path }
            return $name
        }
    }
    return $null
}

function Ensure-VenvPython([string]$Root, [string]$Uv) {
    $venvDir = Join-Path $Root ".venv"
    $venvPython = Join-Path $venvDir "Scripts\python.exe"
    if (Test-Path $venvPython) {
        return $venvPython
    }

    Write-Step "Creating .venv"

    if ($Uv) {
        Invoke-CommandChecked $Uv "venv" "--python" "3.12" $venvDir
        if (Test-Path $venvPython) {
            return $venvPython
        }
    }

    $created = $false
    foreach ($candidate in @(
        @("py.exe", "-3.12", "-m", "venv", $venvDir),
        @("py", "-3.12", "-m", "venv", $venvDir),
        @("python.exe", "-m", "venv", $venvDir),
        @("python", "-m", "venv", $venvDir)
    )) {
        $exe = Find-CommandPath @($candidate[0])
        if (-not $exe) { continue }
        try {
            & $exe @($candidate[1..($candidate.Count - 1)])
            if ($LASTEXITCODE -eq 0 -and (Test-Path $venvPython)) {
                $created = $true
                break
            }
        } catch {
            $created = $false
        }
    }

    if (-not $created -or -not (Test-Path $venvPython)) {
        Fail "Failed to create .venv. Install Python 3.12+ or install uv."
    }
    return $venvPython
}

function Ensure-PythonDependencies([string]$Python, [string]$Uv, [string]$Root) {
    $requirements = Join-Path $Root "requirements-webui.txt"

    if ($SkipInstall) {
        Write-Step "Skipping Python dependency installation"
        & $Python -c "import webview, PyInstaller" 2>$null
        if ($LASTEXITCODE -ne 0) {
            Fail "Required Python build packages are missing. Re-run without -SkipInstall."
        }
        return
    }

    if ($Uv) {
        Write-Step "Installing Python dependencies with uv"
        Invoke-CommandChecked $Uv "pip" "install" "--python" $Python "-r" $requirements
        Invoke-CommandChecked $Uv "pip" "install" "--python" $Python "pyinstaller"
        return
    }

    Write-Step "Installing Python dependencies with pip"
    & $Python -m pip --version *> $null
    if ($LASTEXITCODE -ne 0) {
        & $Python -m ensurepip --upgrade
        if ($LASTEXITCODE -ne 0) {
            Fail "Neither uv nor pip is available for the selected Python environment."
        }
    }
    Invoke-CommandChecked $Python "-m" "pip" "install" "-r" $requirements
    Invoke-CommandChecked $Python "-m" "pip" "install" "pyinstaller"
}

function Ensure-FrontendDependencies([string]$Npm, [string]$Frontend) {
    $nodeModules = Join-Path $Frontend "node_modules"
    if ($SkipInstall) {
        if (-not (Test-Path $nodeModules)) {
            Fail "frontend\node_modules is missing. Re-run without -SkipInstall."
        }
        return
    }

    if (-not (Test-Path $nodeModules)) {
        Write-Step "Installing frontend dependencies"
        Push-Location $Frontend
        try {
            Invoke-CommandChecked $Npm "install" "--no-audit" "--no-fund"
        } finally {
            Pop-Location
        }
    }
}

function Build-Frontend([string]$Npm, [string]$Frontend) {
    Write-Step "Building React / TypeScript UI"
    Push-Location $Frontend
    try {
        Invoke-CommandChecked $Npm "run" "build"
    } finally {
        Pop-Location
    }
}

function Read-AppVersion([string]$Root) {
    $metadata = Join-Path $Root "app_metadata.py"
    if (-not (Test-Path $metadata)) {
        return "dev"
    }
    $text = Get-Content $metadata -Raw -Encoding UTF8
    if ($text -match 'APP_VERSION\s*=\s*["'']([^"'']+)["'']') {
        return $Matches[1]
    }
    return "dev"
}

$Root = Get-RepoRoot
Set-Location $Root

Write-Step "AdopyHzEditor Web UI release build"
Write-Host "Root: $Root"

foreach ($required in @(
    "web_ui.py",
    "app_metadata.py",
    "core\audio_analysis.py",
    "core\audio_player.py",
    "web\backend.py",
    "frontend\package.json",
    "requirements-webui.txt",
    "locales"
)) {
    if (-not (Test-Path (Join-Path $Root $required))) {
        Fail "Required file/folder not found: $required"
    }
}

$Uv = Find-CommandPath @("uv.exe", "uv")
$Npm = Find-CommandPath @("npm.cmd", "npm.exe", "npm")
if (-not $Npm) {
    Fail "npm was not found. Install Node.js 22+ first."
}

$Python = Ensure-VenvPython $Root $Uv
Write-Host "Python: $Python"
if ($Uv) {
    Write-Host "Python packages: uv ($Uv)"
} else {
    Write-Host "Python packages: pip fallback"
}
Write-Host "npm: $Npm"

Ensure-PythonDependencies $Python $Uv $Root

$Frontend = Join-Path $Root "frontend"
Ensure-FrontendDependencies $Npm $Frontend
Build-Frontend $Npm $Frontend

$FrontendDist = Join-Path $Frontend "dist"
$FrontendIndex = Join-Path $FrontendDist "index.html"
if (-not (Test-Path $FrontendIndex)) {
    Fail "Frontend build completed but frontend\dist\index.html was not found."
}

$AppVersion = Read-AppVersion $Root
if ([string]::IsNullOrWhiteSpace($Version)) {
    $Version = $AppVersion
} else {
    $Version = $Version.Trim()
    if ($Version.StartsWith("v")) { $Version = $Version.Substring(1) }
    if ($AppVersion -ne "dev" -and $Version -ne $AppVersion) {
        Fail "Requested version $Version does not match app_metadata.py version $AppVersion."
    }
}
$VersionTag = if ($Version.StartsWith("v")) { $Version } else { "v$Version" }
Write-Host "Version: $VersionTag"

if ($Clean) {
    Write-Step "Cleaning PyInstaller build output"
    Remove-Item -Recurse -Force (Join-Path $Root "build") -ErrorAction SilentlyContinue
    Remove-Item -Recurse -Force (Join-Path $Root "dist") -ErrorAction SilentlyContinue
}

Write-Step "Running PyInstaller for the current Web UI"
$addFrontend = "$FrontendDist;frontend\dist"
$addLocales = "$(Join-Path $Root 'locales');locales"
$pyiArgs = @(
    "web_ui.py",
    "--name", "AdopyHzEditor",
    "--windowed",
    "--noconfirm",
    "--add-data", $addFrontend,
    "--add-data", $addLocales,
    "--collect-all", "webview",
    "--collect-all", "librosa",
    "--collect-all", "soundfile",
    "--collect-all", "sounddevice",
    "--collect-all", "audioread",
    "--collect-all", "mido",
    "--exclude-module", "PySide6",
    "--exclude-module", "PyQt5",
    "--exclude-module", "PyQt6",
    "--exclude-module", "pyqtgraph"
)
if ($Clean) {
    $pyiArgs += "--clean"
}
Invoke-CommandChecked $Python "-m" "PyInstaller" @pyiArgs

$DistApp = Join-Path $Root "dist\AdopyHzEditor"
$Exe = Join-Path $DistApp "AdopyHzEditor.exe"
if (-not (Test-Path $Exe)) {
    Fail "Build finished but exe was not found: $Exe"
}

$bundledIndexes = @(
    (Join-Path $DistApp "_internal\frontend\dist\index.html"),
    (Join-Path $DistApp "frontend\dist\index.html")
)
if (-not ($bundledIndexes | Where-Object { Test-Path $_ } | Select-Object -First 1)) {
    Fail "Build finished but the bundled React UI was not found."
}
Write-Ok "Current Web UI exe built: $Exe"

if (-not $NoZip) {
    Write-Step "Creating release zip"
    $ReleaseDir = Join-Path $Root "releases"
    New-Item -ItemType Directory -Force -Path $ReleaseDir | Out-Null
    $ZipPath = Join-Path $ReleaseDir "AdopyHzEditor_Windows_$VersionTag.zip"
    Remove-Item -Force $ZipPath -ErrorAction SilentlyContinue
    Compress-Archive -Path $DistApp -DestinationPath $ZipPath -Force
    Write-Ok "Release zip: $ZipPath"
}
