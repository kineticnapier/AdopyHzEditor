from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Iterable

STEAM_APP_ID = "977950"
DEFAULT_INSTALL_DIR = "A Dance of Fire and Ice"
_EXTRACTOR_NAME = "AdopyHzEditor.AssetExtractor.exe"
_VDF_PATH_RE = re.compile(r'"path"\s*"((?:\\.|[^"])*)"', re.IGNORECASE)
_INSTALL_DIR_RE = re.compile(r'"installdir"\s*"((?:\\.|[^"])*)"', re.IGNORECASE)


def is_adofai_root(path: str | Path) -> bool:
    try:
        root = Path(path).expanduser().resolve()
    except (OSError, RuntimeError, ValueError):
        return False
    data = root / "A Dance of Fire and Ice_Data"
    return (
        (data / "resources.assets").is_file()
        and (data / "resources.assets.resS").is_file()
    )


def _unescape_vdf(value: str) -> str:
    return value.replace("\\\\", "\\").replace('\\"', '"')


def _registry_steam_roots() -> Iterable[Path]:
    if os.name != "nt":
        return ()
    try:
        import winreg
    except ImportError:
        return ()

    locations = (
        (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam", "InstallPath"),
    )
    roots: list[Path] = []
    for hive, key_name, value_name in locations:
        try:
            with winreg.OpenKey(hive, key_name) as key:
                value, _ = winreg.QueryValueEx(key, value_name)
            if value:
                roots.append(Path(str(value)))
        except OSError:
            continue
    return roots


def _steam_roots() -> list[Path]:
    candidates: list[Path] = []
    explicit = os.environ.get("STEAM_PATH")
    if explicit:
        candidates.append(Path(explicit))
    candidates.extend(_registry_steam_roots())

    for env_name in ("PROGRAMFILES(X86)", "PROGRAMFILES"):
        base = os.environ.get(env_name)
        if base:
            candidates.append(Path(base) / "Steam")

    seen: set[str] = set()
    result: list[Path] = []
    for candidate in candidates:
        try:
            normalized = candidate.expanduser().resolve()
        except (OSError, RuntimeError, ValueError):
            continue
        key = os.path.normcase(str(normalized))
        if key in seen:
            continue
        seen.add(key)
        result.append(normalized)
    return result


def _library_roots(steam_root: Path) -> list[Path]:
    roots = [steam_root]
    vdf = steam_root / "steamapps" / "libraryfolders.vdf"
    try:
        text = vdf.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return roots

    for match in _VDF_PATH_RE.finditer(text):
        raw = _unescape_vdf(match.group(1))
        if raw:
            roots.append(Path(raw))

    seen: set[str] = set()
    unique: list[Path] = []
    for root in roots:
        try:
            normalized = root.expanduser().resolve()
        except (OSError, RuntimeError, ValueError):
            continue
        key = os.path.normcase(str(normalized))
        if key in seen:
            continue
        seen.add(key)
        unique.append(normalized)
    return unique


def _install_from_manifest(library_root: Path) -> Path | None:
    manifest = library_root / "steamapps" / f"appmanifest_{STEAM_APP_ID}.acf"
    try:
        text = manifest.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    match = _INSTALL_DIR_RE.search(text)
    if not match:
        return None
    install_dir = _unescape_vdf(match.group(1)).strip()
    if not install_dir:
        return None
    candidate = library_root / "steamapps" / "common" / install_dir
    return candidate.resolve() if is_adofai_root(candidate) else None


def find_adofai_installation() -> Path | None:
    explicit = os.environ.get("ADOPYHZ_ADOFAI_PATH")
    if explicit and is_adofai_root(explicit):
        return Path(explicit).expanduser().resolve()

    for steam_root in _steam_roots():
        for library_root in _library_roots(steam_root):
            from_manifest = _install_from_manifest(library_root)
            if from_manifest is not None:
                return from_manifest

            fallback = library_root / "steamapps" / "common" / DEFAULT_INSTALL_DIR
            if is_adofai_root(fallback):
                return fallback.resolve()
    return None


def _local_app_data() -> Path:
    value = os.environ.get("LOCALAPPDATA")
    if value:
        return Path(value)
    return Path.home() / "AppData" / "Local"


def adofai_kick_cache_path() -> Path:
    return _local_app_data() / "AdopyHzEditor" / "AssetCache" / "hitsounds" / "sndKick.wav"


def _cache_manifest_path() -> Path:
    return adofai_kick_cache_path().with_name("sndKick.source.json")


def _source_signature(game_root: Path) -> dict[str, object]:
    data = game_root / "A Dance of Fire and Ice_Data"
    result: dict[str, object] = {"gameRoot": str(game_root)}
    for name in ("resources.assets", "resources.assets.resS"):
        path = data / name
        stat = path.stat()
        result[name] = {"size": stat.st_size, "mtimeNs": stat.st_mtime_ns}
    return result


def _cached_signature_matches(game_root: Path) -> bool:
    kick = adofai_kick_cache_path()
    manifest = _cache_manifest_path()
    if not kick.is_file() or kick.stat().st_size <= 44 or not manifest.is_file():
        return False
    try:
        saved = json.loads(manifest.read_text(encoding="utf-8"))
        return saved == _source_signature(game_root)
    except (OSError, ValueError, json.JSONDecodeError):
        return False


def _extractor_project() -> Path:
    return Path(__file__).resolve().parents[1] / "tools" / "AdopyHzEditor.AssetExtractor" / "AdopyHzEditor.AssetExtractor.csproj"


def _extractor_candidates() -> list[Path]:
    candidates: list[Path] = []
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent / "AssetExtractor" / _EXTRACTOR_NAME)

    project = _extractor_project().parent
    candidates.extend(
        [
            project / "bin" / "Release" / "net8.0" / "win-x64" / "publish" / _EXTRACTOR_NAME,
            project / "bin" / "Release" / "net8.0" / "win-x64" / _EXTRACTOR_NAME,
        ]
    )
    return candidates


def _run_extractor(game_root: Path, output_path: Path) -> None:
    args = ["--adofai", str(game_root), "--output", str(output_path)]
    extractor = next((p for p in _extractor_candidates() if p.is_file()), None)

    if extractor is not None:
        command = [str(extractor), *args]
    else:
        dotnet = shutil.which("dotnet")
        project = _extractor_project()
        if dotnet is None or not project.is_file():
            raise RuntimeError(
                "ADOFAI Kick extractor is unavailable. Reinstall the packaged build "
                "or install .NET 8 SDK for a source checkout."
            )
        command = [
            dotnet,
            "run",
            "--project",
            str(project),
            "-c",
            "Release",
            "--",
            *args,
        ]

    completed = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=600,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        if len(detail) > 1200:
            detail = detail[-1200:]
        raise RuntimeError(
            f"ADOFAI Kick extraction failed (exit {completed.returncode}): {detail}"
        )


def ensure_adofai_kick(*, force: bool = False) -> Path:
    game_root = find_adofai_installation()
    if game_root is None:
        raise FileNotFoundError(
            "ADOFAI installation was not found. Set ADOPYHZ_ADOFAI_PATH to the game directory."
        )

    if not force and _cached_signature_matches(game_root):
        return adofai_kick_cache_path()

    kick = adofai_kick_cache_path()
    kick.parent.mkdir(parents=True, exist_ok=True)
    _run_extractor(game_root, kick)

    if not kick.is_file() or kick.stat().st_size <= 44:
        raise RuntimeError("ADOFAI Kick extractor finished without a valid sndKick.wav.")

    manifest = _cache_manifest_path()
    temp = manifest.with_suffix(manifest.suffix + ".tmp")
    temp.write_text(
        json.dumps(_source_signature(game_root), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temp.replace(manifest)
    return kick
