param(
    [switch]$Dev,
    [switch]$SkipBuild,
    [switch]$NoInstall
)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$Frontend = Join-Path $Root "frontend"

function Resolve-PythonCommand {
    $venvPython = Join-Path $Root ".venv\Scripts\python.exe"
    if (Test-Path $venvPython) {
        return @{ Exe = $venvPython; Prefix = @() }
    }

    $python = Get-Command python.exe -ErrorAction SilentlyContinue
    if (-not $python) {
        $python = Get-Command python -ErrorAction SilentlyContinue
    }
    if ($python) {
        return @{ Exe = $python.Source; Prefix = @() }
    }

    $py = Get-Command py.exe -ErrorAction SilentlyContinue
    if (-not $py) {
        $py = Get-Command py -ErrorAction SilentlyContinue
    }
    if ($py) {
        return @{ Exe = $py.Source; Prefix = @("-3") }
    }

    throw "Python 3 が見つかりません。.venv を作成するか Python を PATH に追加してください。"
}

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)][string]$Exe,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [string]$WorkingDirectory = $Root
    )

    Push-Location $WorkingDirectory
    try {
        & $Exe @Arguments
        if ($LASTEXITCODE -ne 0) {
            throw "コマンドが終了コード $LASTEXITCODE で失敗しました: $Exe $($Arguments -join ' ')"
        }
    }
    finally {
        Pop-Location
    }
}

function Invoke-Python {
    param([Parameter(Mandatory = $true)][string[]]$Arguments)
    Invoke-Checked -Exe $Python.Exe -Arguments @($Python.Prefix + $Arguments) -WorkingDirectory $Root
}

function Test-PythonDependencies {
    Push-Location $Root
    try {
        & $Python.Exe @($Python.Prefix + @("-c", "import web_ui")) *> $null
        return $LASTEXITCODE -eq 0
    }
    finally {
        Pop-Location
    }
}

function Wait-Vite {
    param([string]$Url)
    for ($i = 0; $i -lt 60; $i++) {
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 1
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
                return
            }
        }
        catch {
            Start-Sleep -Milliseconds 250
        }
    }
    throw "Vite 開発サーバーが起動しませんでした: $Url"
}

Set-Location $Root
$Python = Resolve-PythonCommand
$npm = Get-Command npm.cmd -ErrorAction SilentlyContinue
if (-not $npm) {
    $npm = Get-Command npm -ErrorAction SilentlyContinue
}
if (-not $npm) {
    throw "npm が見つかりません。Node.js をインストールして PATH に追加してください。"
}

Write-Host "AdopyHzEditor Web UI" -ForegroundColor Cyan
Write-Host "Python: $($Python.Exe)"

if (-not $NoInstall) {
    if (-not (Test-Path (Join-Path $Frontend "node_modules"))) {
        Write-Host "[1/3] frontend 依存関係をインストールしています..." -ForegroundColor Yellow
        Invoke-Checked -Exe $npm.Source -Arguments @("install", "--no-audit", "--no-fund") -WorkingDirectory $Frontend
    }

    if (-not (Test-PythonDependencies)) {
        Write-Host "[1/3] Python 依存関係をインストールしています..." -ForegroundColor Yellow
        Invoke-Python -Arguments @("-m", "pip", "install", "-r", "requirements-webui.txt")
        if (-not (Test-PythonDependencies)) {
            throw "Python 依存関係をインストールしましたが web_ui を読み込めませんでした。"
        }
    }
}

if ($Dev) {
    $url = "http://127.0.0.1:5173"
    Write-Host "[2/3] Vite 開発サーバーを起動しています..." -ForegroundColor Yellow
    $vite = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "npm run dev -- --host 127.0.0.1" -WorkingDirectory $Frontend -PassThru
    try {
        Wait-Vite -Url $url
        $env:ADOPY_WEB_UI_URL = $url
        Write-Host "[3/3] web_ui.py を起動します ($url)" -ForegroundColor Green
        Invoke-Python -Arguments @("web_ui.py")
    }
    finally {
        Remove-Item Env:ADOPY_WEB_UI_URL -ErrorAction SilentlyContinue
        if ($vite -and -not $vite.HasExited) {
            try {
                & taskkill.exe /PID $vite.Id /T /F *> $null
            }
            catch {
                Stop-Process -Id $vite.Id -Force -ErrorAction SilentlyContinue
            }
        }
    }
    exit 0
}

if (-not $SkipBuild) {
    Write-Host "[2/3] React / TypeScript UI をビルドしています..." -ForegroundColor Yellow
    Invoke-Checked -Exe $npm.Source -Arguments @("run", "build") -WorkingDirectory $Frontend
}
elseif (-not (Test-Path (Join-Path $Frontend "dist\index.html"))) {
    throw "-SkipBuild が指定されていますが frontend/dist/index.html がありません。"
}

Write-Host "[3/3] web_ui.py を起動します..." -ForegroundColor Green
Invoke-Python -Arguments @("web_ui.py")
