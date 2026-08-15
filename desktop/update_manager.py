\
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.request


@dataclass
class ReleaseAsset:
    name: str
    browser_download_url: str
    size: int = 0


@dataclass
class UpdateInfo:
    current_version: str
    latest_version: str
    release_name: str
    html_url: str
    body: str
    asset: ReleaseAsset | None

    @property
    def is_available(self) -> bool:
        return compare_versions(self.latest_version, self.current_version) > 0


def normalize_version(v: str) -> str:
    v = (v or "").strip()
    if v.lower().startswith("v"):
        v = v[1:]
    return v


def version_tuple(v: str) -> tuple[int, ...]:
    v = normalize_version(v)
    parts = re.findall(r"\d+", v)
    if not parts:
        return (0,)
    return tuple(int(x) for x in parts[:4])


def compare_versions(a: str, b: str) -> int:
    ta = list(version_tuple(a))
    tb = list(version_tuple(b))
    n = max(len(ta), len(tb))
    ta += [0] * (n - len(ta))
    tb += [0] * (n - len(tb))
    return (ta > tb) - (ta < tb)


def fetch_latest_release(api_url: str, *, timeout: float = 10.0) -> dict:
    req = urllib.request.Request(
        api_url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "AdopyHzEditor-Updater",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return json.loads(res.read().decode("utf-8"))


def choose_windows_zip_asset(release: dict) -> ReleaseAsset | None:
    assets = release.get("assets") or []
    candidates: list[tuple[int, ReleaseAsset]] = []
    for a in assets:
        name = str(a.get("name") or "")
        url = str(a.get("browser_download_url") or "")
        if not name.lower().endswith(".zip") or not url:
            continue
        lname = name.lower()
        score = 0
        if "windows" in lname or "win" in lname:
            score += 10
        if "adopyhzeditor" in lname:
            score += 5
        if "source" in lname:
            score -= 20
        candidates.append((score, ReleaseAsset(name=name, browser_download_url=url, size=int(a.get("size") or 0))))

    if not candidates:
        return None

    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


def check_for_update(current_version: str, api_url: str) -> UpdateInfo:
    release = fetch_latest_release(api_url)
    latest = normalize_version(str(release.get("tag_name") or release.get("name") or "0.0.0"))
    asset = choose_windows_zip_asset(release)
    return UpdateInfo(
        current_version=normalize_version(current_version),
        latest_version=latest,
        release_name=str(release.get("name") or release.get("tag_name") or latest),
        html_url=str(release.get("html_url") or ""),
        body=str(release.get("body") or ""),
        asset=asset,
    )


def download_file(url: str, dst: Path, *, timeout: float = 30.0) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "AdopyHzEditor-Updater"})
    with urllib.request.urlopen(req, timeout=timeout) as res:
        with dst.open("wb") as f:
            while True:
                chunk = res.read(1024 * 256)
                if not chunk:
                    break
                f.write(chunk)


def write_windows_update_script(*, zip_path: Path, target_dir: Path, exe_path: Path, pid: int) -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="adopyhz_update_"))
    script = tmp / "apply_update.bat"
    extract_dir = tmp / "extracted"
    ps_path = tmp / "apply_update.ps1"

    ps = f"""
$ErrorActionPreference = "Stop"
try {{
  Wait-Process -Id {int(pid)} -ErrorAction SilentlyContinue
}} catch {{}}
Start-Sleep -Milliseconds 700

$zip = "{str(zip_path)}"
$extract = "{str(extract_dir)}"
$target = "{str(target_dir)}"
$exe = "{str(exe_path)}"

if (Test-Path $extract) {{ Remove-Item $extract -Recurse -Force }}
New-Item -ItemType Directory -Path $extract | Out-Null
Expand-Archive -Path $zip -DestinationPath $extract -Force

$items = Get-ChildItem -Path $extract
if (($items.Count -eq 1) -and $items[0].PSIsContainer) {{
  $src = $items[0].FullName
}} else {{
  $src = $extract
}}

Copy-Item -Path (Join-Path $src "*") -Destination $target -Recurse -Force

if (Test-Path $exe) {{
  Start-Process -FilePath $exe
}}

try {{ Remove-Item $zip -Force }} catch {{}}
try {{ Remove-Item $extract -Recurse -Force }} catch {{}}
"""
    ps_path.write_text(ps, encoding="utf-8")

    bat = (
        "@echo off\n"
        "setlocal\n"
        f'powershell -NoProfile -ExecutionPolicy Bypass -File "{ps_path}"\n'
        f'del "{ps_path}" > nul 2> nul\n'
        'del "%~f0" > nul 2> nul\n'
    )
    script.write_text(bat, encoding="utf-8")
    return script


def start_apply_update(zip_path: Path) -> None:
    if not getattr(sys, "frozen", False):
        raise RuntimeError("Automatic apply/restart is available only in PyInstaller exe builds.")
    exe_path = Path(sys.executable).resolve()
    target_dir = exe_path.parent
    script = write_windows_update_script(
        zip_path=zip_path.resolve(),
        target_dir=target_dir.resolve(),
        exe_path=exe_path,
        pid=os.getpid(),
    )

    if sys.platform.startswith("win"):
        subprocess.Popen(
            ["cmd", "/c", "start", "", str(script)],
            cwd=str(script.parent),
            close_fds=True,
            creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
        )
    else:
        raise RuntimeError("Automatic apply/restart is currently implemented only for Windows builds.")
