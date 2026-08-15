# release.ps1
# Prepare and publish a tagged AdopyHzEditor release.
# The tag triggers .github/workflows/release.yml, which rebuilds the Windows
# package on GitHub Actions and publishes the ZIP as a GitHub Release asset.
#
# Usage:
#   .\scripts\release.ps1 -Version 0.8.0
#   .\scripts\release.ps1 -Version 0.8.0 -NoPush

param(
    [Parameter(Mandatory=$true)][string]$Version,
    [switch]$NoPush
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Fail([string]$Message) {
    Write-Host "ERROR: $Message" -ForegroundColor Red
    exit 1
}

function Invoke-GitChecked([string[]]$Arguments) {
    & git @Arguments
    if ($LASTEXITCODE -ne 0) {
        Fail "git command failed: git $($Arguments -join ' ')"
    }
}

$scriptDir = Split-Path -Parent $PSCommandPath
$Root = (Resolve-Path (Join-Path $scriptDir "..")).Path
Set-Location $Root

$Version = $Version.Trim()
if ($Version.StartsWith("v")) {
    $Version = $Version.Substring(1)
}
if ($Version -notmatch '^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$') {
    Fail "Version must look like 0.8.0 or 0.8.0-beta.1."
}
$Tag = "v$Version"

$branch = (& git branch --show-current).Trim()
if ($LASTEXITCODE -ne 0) { Fail "Could not determine the current Git branch." }
if ($branch -ne "main") {
    Fail "Releases must be created from main. Current branch: $branch"
}

$status = & git status --porcelain
if ($LASTEXITCODE -ne 0) { Fail "Could not inspect the Git working tree." }
if ($status) {
    Fail "Working tree is not clean. Commit or stash changes before releasing."
}

& git rev-parse --verify --quiet "refs/tags/$Tag" *> $null
if ($LASTEXITCODE -eq 0) {
    Fail "Tag already exists locally: $Tag"
}

$remoteTag = & git ls-remote --tags origin "refs/tags/$Tag"
if ($LASTEXITCODE -ne 0) { Fail "Could not query origin tags." }
if ($remoteTag) {
    Fail "Tag already exists on origin: $Tag"
}

$metadataPath = Join-Path $Root "app_metadata.py"
if (-not (Test-Path $metadataPath)) {
    Fail "app_metadata.py was not found."
}

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$originalMetadata = [System.IO.File]::ReadAllText($metadataPath)
$updatedMetadata = [regex]::Replace(
    $originalMetadata,
    'APP_VERSION\s*=\s*["''][^"'']+["'']',
    "APP_VERSION = `"$Version`"",
    1
)
if ($updatedMetadata -eq $originalMetadata -and $originalMetadata -notmatch "APP_VERSION\s*=\s*`"$([regex]::Escape($Version))`"") {
    Fail "Could not update APP_VERSION in app_metadata.py."
}

[System.IO.File]::WriteAllText($metadataPath, $updatedMetadata, $utf8NoBom)

try {
    Write-Host "Preflight build for $Tag" -ForegroundColor Cyan
    & (Join-Path $scriptDir "build_release.ps1") -Clean -Version $Version
    if ($LASTEXITCODE -ne 0) {
        throw "Release build failed."
    }
} catch {
    [System.IO.File]::WriteAllText($metadataPath, $originalMetadata, $utf8NoBom)
    throw
}

Invoke-GitChecked @("add", "app_metadata.py")
Invoke-GitChecked @("commit", "-m", "Release $Tag")
Invoke-GitChecked @("tag", "-a", $Tag, "-m", "AdopyHzEditor $Tag")

if ($NoPush) {
    Write-Host "Created local release commit and tag $Tag. Push was skipped." -ForegroundColor Yellow
    Write-Host "To publish later: git push origin main; git push origin $Tag"
    exit 0
}

Invoke-GitChecked @("push", "origin", "main")
Invoke-GitChecked @("push", "origin", $Tag)

Write-Host "Published tag $Tag." -ForegroundColor Green
Write-Host "GitHub Actions will build the Windows Web UI package and create the GitHub Release."
