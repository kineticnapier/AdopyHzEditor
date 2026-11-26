"""App-wide preferences, kept apart from the settings saved in each project.

They live in the same ``settings.json`` as the UI language, under the
``"preferences"`` key, so one file holds everything the app remembers.
"""

from __future__ import annotations

import json
import re
import threading
import urllib.request
from pathlib import Path
from typing import Any

from app_metadata import APP_NAME, APP_VERSION, GITHUB_LATEST_RELEASE_API, GITHUB_RELEASES_URL
from exporters.adofai_kps import HUMAN_KPS_LIMIT
from i18n import available_languages, current_language, set_language
from web.io import DEFAULT_EDITOR_SETTINGS

PREFERENCES_KEY = "preferences"

# Project settings a new project starts from.  Everything else keeps the
# built-in default.
NEW_PROJECT_KEYS: tuple[str, ...] = (
    "bpm",
    "gridEnabled",
    "snapEnabled",
    "snapDiv",
    "exportOctave",
    "previewSound",
    "previewVolume",
    "colormap",
)

# ADOFAI export options that depend on the document, not on taste, and so are
# never saved as defaults.
EXPORT_DOCUMENT_KEYS = frozenset({
    "projectBpm",
    "angleOnlyBpm",
    "targetBpm",
    "useProjectSong",
    "copyProjectSong",
    "songOffsetMs",
    "fullSongOffsetMs",
    "selectedSongOffsetMs",
    "selectedOnly",
    "songSourcePath",
    "harmonyTuning",
})

KPS_LIMIT_RANGE = (1.0, 100000.0)
UPDATE_TIMEOUT_SECONDS = 5.0

_file_lock = threading.Lock()


def _read_file(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def parse_preferences(raw: Any) -> dict[str, Any]:
    """Saved preferences, with defaults for anything missing or broken."""
    raw = raw if isinstance(raw, dict) else {}
    new_project = raw.get("newProject")
    export = raw.get("adofaiExport")
    last = raw.get("lastProject")
    try:
        kps = float(raw.get("kpsLimit", HUMAN_KPS_LIMIT))
    except (TypeError, ValueError):
        kps = HUMAN_KPS_LIMIT
    if not (KPS_LIMIT_RANGE[0] <= kps <= KPS_LIMIT_RANGE[1]):
        kps = HUMAN_KPS_LIMIT
    return {
        "newProject": {k: v for k, v in new_project.items() if k in NEW_PROJECT_KEYS}
        if isinstance(new_project, dict) else {},
        "adofaiExport": {k: v for k, v in export.items() if k not in EXPORT_DOCUMENT_KEYS}
        if isinstance(export, dict) else {},
        "kpsLimit": kps,
        "checkUpdates": bool(raw.get("checkUpdates", False)),
        "reopenLastProject": bool(raw.get("reopenLastProject", False)),
        "lastProject": str(last) if isinstance(last, str) and last else None,
    }


def load_preferences(path: Path) -> dict[str, Any]:
    return parse_preferences(_read_file(path).get(PREFERENCES_KEY))


def save_preferences(path: Path, prefs: dict[str, Any]) -> None:
    """Write ``prefs`` beside the language, keeping any other keys in the file."""
    with _file_lock:
        data = _read_file(path)
        data[PREFERENCES_KEY] = prefs
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)


def _version_tuple(text: str) -> tuple[int, ...]:
    return tuple(int(part) for part in re.findall(r"\d+", text.split("-", 1)[0].split("+", 1)[0])[:3])


def is_newer_version(latest: str, current: str = APP_VERSION) -> bool:
    try:
        return _version_tuple(latest.lstrip("vV")) > _version_tuple(current.lstrip("vV"))
    except ValueError:
        return False


def fetch_latest_release(timeout: float = UPDATE_TIMEOUT_SECONDS) -> dict[str, Any]:
    """The newest published release on GitHub (only the public API is asked)."""
    request = urllib.request.Request(
        GITHUB_LATEST_RELEASE_API,
        headers={"Accept": "application/vnd.github+json", "User-Agent": f"{APP_NAME}/{APP_VERSION}"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed https URL
        data = json.loads(response.read().decode("utf-8"))
    tag = str(data.get("tag_name") or "").strip()
    if not tag:
        raise ValueError("release has no tag")
    return {"version": tag.lstrip("vV"), "url": str(data.get("html_url") or GITHUB_RELEASES_URL)}


class PreferencesMixin:
    """Bridge APIs for the 環境設定 dialog and what it changes at startup."""

    _startup_applied = False
    # Set by the app's entry point.  Without it (as in tests) preferences are
    # kept in memory only, so nothing reads or writes the user's own file.
    _preferences_file: Path | None = None
    _preferences_memory: dict[str, Any] | None = None

    def _load_prefs(self) -> dict[str, Any]:
        if self._preferences_file is not None:
            return load_preferences(self._preferences_file)
        return parse_preferences(self._preferences_memory)

    def _save_prefs(self, prefs: dict[str, Any]) -> None:
        if self._preferences_file is not None:
            save_preferences(self._preferences_file, prefs)
        else:
            self._preferences_memory = json.loads(json.dumps(prefs))

    # -- reading / writing ------------------------------------------------
    def get_preferences(self) -> dict[str, Any]:
        prefs = self._load_prefs()
        return {
            "language": current_language(),
            "languages": available_languages(),
            "newProject": prefs["newProject"],
            "newProjectBuiltin": {key: DEFAULT_EDITOR_SETTINGS[key] for key in NEW_PROJECT_KEYS},
            "kpsLimit": prefs["kpsLimit"],
            "hasExportDefaults": bool(prefs["adofaiExport"]),
            "checkUpdates": prefs["checkUpdates"],
            "reopenLastProject": prefs["reopenLastProject"],
            "lastProject": prefs["lastProject"],
        }

    def set_preferences(self, changes: dict[str, Any]) -> dict[str, Any]:
        """Validate the whole batch, then save it; unknown keys are ignored."""
        if not isinstance(changes, dict):
            raise TypeError("changes must be an object")
        prefs = self._load_prefs()
        language = None
        if "language" in changes:
            language = str(changes["language"]).lower()
            if language not in available_languages():
                raise ValueError(f"unknown language: {language}")
        if "newProject" in changes:
            values = changes["newProject"]
            if not isinstance(values, dict):
                raise TypeError("newProject must be an object")
            prefs["newProject"] = {
                key: self._normalize_setting(key, value)
                for key, value in values.items()
                if key in NEW_PROJECT_KEYS
            }
        if "kpsLimit" in changes:
            kps = float(changes["kpsLimit"])
            if not (KPS_LIMIT_RANGE[0] <= kps <= KPS_LIMIT_RANGE[1]):
                raise ValueError("kpsLimit is out of range")
            prefs["kpsLimit"] = kps
        for key in ("checkUpdates", "reopenLastProject"):
            if key in changes:
                prefs[key] = bool(changes[key])
        self._save_prefs(prefs)
        if language is not None and language != current_language():
            set_language(language, save=self._preferences_file is not None)
        return self.get_preferences()

    # -- ADOFAI export ----------------------------------------------------
    def save_adofai_export_defaults(self, options: dict[str, Any]) -> dict[str, Any]:
        """Keep the dialog's current choices as the defaults for next time."""
        if not isinstance(options, dict):
            raise TypeError("options must be an object")
        known = self.get_adofai_export_defaults()
        saved = {
            key: value
            for key, value in options.items()
            if key in known and key not in EXPORT_DOCUMENT_KEYS and isinstance(value, type(known[key]))
        }
        prefs = self._load_prefs()
        prefs["adofaiExport"] = saved
        self._save_prefs(prefs)
        return {"ok": True, "saved": len(saved)}

    def clear_adofai_export_defaults(self) -> dict[str, Any]:
        prefs = self._load_prefs()
        prefs["adofaiExport"] = {}
        self._save_prefs(prefs)
        return self.get_preferences()

    def _saved_adofai_export_defaults(self, defaults: dict[str, Any]) -> dict[str, Any]:
        """``defaults`` with the saved choices laid over it (matching types only)."""
        saved = self._load_prefs()["adofaiExport"]
        out = dict(defaults)
        for key, value in saved.items():
            if key in out and key not in EXPORT_DOCUMENT_KEYS and isinstance(value, type(out[key])):
                out[key] = value
        return out

    def _kps_limit(self) -> float:
        return float(self._load_prefs()["kpsLimit"])

    # -- startup ----------------------------------------------------------
    def _remember_last_project(self, path: str) -> None:
        try:
            prefs = self._load_prefs()
            prefs["lastProject"] = str(Path(path).resolve())
            self._save_prefs(prefs)
        except OSError:
            pass

    def apply_startup_preferences(self) -> dict[str, Any]:
        """Run once when the window opens: new-project defaults, then reopening.

        Only an untouched startup document is changed, so a second call (a
        reloaded page) never overwrites work.
        """
        prefs = self._load_prefs()
        reopened = None
        reopen_error = None
        with self._lock:
            first = not self._startup_applied
            self._startup_applied = True
            pristine = first and not self.notes and not self.audio_path and not self.project_path and not self._dirty
            if pristine and prefs["newProject"]:
                for key, value in prefs["newProject"].items():
                    if key in self.settings:
                        try:
                            self.settings[key] = self._normalize_setting(key, value)
                        except (TypeError, ValueError):
                            pass
                self._apply_player_settings()
                self._saved_checkpoint = self._document_checkpoint()
        last = prefs["lastProject"]
        if pristine and prefs["reopenLastProject"] and last:
            if Path(last).exists():
                try:
                    self._load_project_path(last)
                    reopened = last
                except Exception as exc:  # a broken file must not stop startup
                    reopen_error = f"前回のプロジェクトを開けませんでした: {exc}"
            else:
                reopen_error = f"前回のプロジェクトが見つかりません: {last}"
        if reopen_error:
            with self._lock:
                self._status = reopen_error
        return {
            "state": self.get_state(),
            "checkUpdates": prefs["checkUpdates"] and first,
            "reopened": reopened,
        }

    def check_for_update(self) -> dict[str, Any]:
        try:
            latest = fetch_latest_release()
        except Exception as exc:
            return {"ok": False, "current": APP_VERSION, "error": str(exc), "url": GITHUB_RELEASES_URL}
        return {
            "ok": True,
            "current": APP_VERSION,
            "latest": latest["version"],
            "newer": is_newer_version(latest["version"]),
            "url": latest["url"],
        }
