from __future__ import annotations

import json
import locale
import sys
from pathlib import Path

_LANG = "en"
_TRANSLATIONS: dict[str, dict[str, str]] = {}


def app_config_dir() -> Path:
    if sys.platform.startswith("win"):
        base = Path.home() / "AppData" / "Roaming"
    else:
        base = Path.home() / ".config"
    return base / "AdopyHzEditor"


def language_config_path() -> Path:
    return app_config_dir() / "settings.json"


def resource_base_dirs() -> list[Path]:
    # Normal source tree, PyInstaller _MEIPASS, and one-folder executable dir.
    candidates = [
        Path(getattr(sys, "_MEIPASS", "")) if getattr(sys, "_MEIPASS", None) else None,
        Path(__file__).resolve().parent,
        Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else None,
    ]
    out: list[Path] = []
    for p in candidates:
        if p is not None and p not in out:
            out.append(p)
    return out


def resource_base_dir() -> Path:
    return resource_base_dirs()[0]


def locale_file(lang: str) -> Path:
    filename = f"{lang}.json"
    for base in resource_base_dirs():
        p = base / "locales" / filename
        if p.exists():
            return p
    return resource_base_dir() / "locales" / filename


def available_languages() -> list[str]:
    langs: set[str] = set()
    for base in resource_base_dirs():
        loc = base / "locales"
        if loc.exists():
            langs.update(p.stem for p in loc.glob("*.json"))
    return sorted(langs) or ["en", "ja"]


def system_default_language() -> str:
    try:
        code = (locale.getlocale()[0] or locale.getdefaultlocale()[0] or "").lower()
    except Exception:
        code = ""
    if code.startswith("ja"):
        return "ja"
    return "en"


def load_app_language() -> str:
    path = language_config_path()
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            lang = str(data.get("language", "")).lower()
            if lang:
                return lang
    except Exception:
        pass
    return system_default_language()


def save_app_language(lang: str) -> None:
    try:
        d = app_config_dir()
        d.mkdir(parents=True, exist_ok=True)
        path = language_config_path()
        data = {}
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                data = {}
        data["language"] = lang
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def load_language(lang: str) -> None:
    global _LANG

    lang = (lang or "en").lower().replace("-", "_")
    if lang.startswith("ja"):
        lang = "ja"
    elif lang.startswith("en"):
        lang = "en"

    path = locale_file(lang)
    if not path.exists():
        lang = "en"
        path = locale_file("en")

    if lang not in _TRANSLATIONS:
        try:
            _TRANSLATIONS[lang] = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            _TRANSLATIONS[lang] = {}

    # Ensure English fallback is loaded.
    if "en" not in _TRANSLATIONS and lang != "en":
        try:
            _TRANSLATIONS["en"] = json.loads(locale_file("en").read_text(encoding="utf-8"))
        except Exception:
            _TRANSLATIONS["en"] = {}

    _LANG = lang


def set_language(lang: str, *, save: bool = True) -> None:
    load_language(lang)
    if save:
        save_app_language(_LANG)


def current_language() -> str:
    return _LANG


def tr(key: str, **kwargs) -> str:
    table = _TRANSLATIONS.get(_LANG, {})
    fallback = _TRANSLATIONS.get("en", {})
    text = table.get(key, fallback.get(key, key))
    if kwargs:
        try:
            text = text.format(**kwargs)
        except Exception:
            pass
    return text


load_language(load_app_language())
