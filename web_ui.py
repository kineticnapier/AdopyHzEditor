from __future__ import annotations

import os
from pathlib import Path
from typing import Any

try:
    import webview
except ImportError as exc:
    raise SystemExit(
        "pywebview is required. Install it with: "
        "python -m pip install -r requirements-webui.txt"
    ) from exc


ROOT = Path(__file__).resolve().parent
DIST_INDEX = ROOT / "frontend" / "dist" / "index.html"


class Bridge:
    """Minimal JS <-> Python bridge for the experimental TypeScript UI."""

    def __init__(self) -> None:
        self._settings: dict[str, Any] = {
            "volume": 85,
            "speed": 1.0,
            "notePreview": True,
            "previewVolume": 20,
            "bpm": 120.0,
            "snapEnabled": False,
        }

    def ping(self) -> dict[str, Any]:
        return {"ok": True, "app": "AdopyHzEditor", "ui": "React + TypeScript"}

    def get_settings(self) -> dict[str, Any]:
        return dict(self._settings)

    def update_settings(self, changes: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(changes, dict):
            raise TypeError("changes must be an object")
        for key, value in changes.items():
            if key in self._settings:
                self._settings[key] = value
        return dict(self._settings)


def _ui_url() -> str:
    dev_url = os.environ.get("ADOPY_WEB_UI_URL", "").strip()
    if dev_url:
        return dev_url
    if not DIST_INDEX.exists():
        raise SystemExit(
            "frontend/dist/index.html is missing. Run:\n"
            "  cd frontend\n  npm install\n  npm run build\n"
            "then: python web_ui.py"
        )
    os.chdir(ROOT)
    return "frontend/dist/index.html"


def main() -> int:
    bridge = Bridge()
    webview.create_window(
        "AdopyHzEditor - Web UI Prototype",
        _ui_url(),
        js_api=bridge,
        width=1360,
        height=820,
        min_size=(980, 620),
        background_color="#20242a",
    )
    webview.start(debug=os.environ.get("ADOPY_WEB_UI_DEBUG") == "1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
