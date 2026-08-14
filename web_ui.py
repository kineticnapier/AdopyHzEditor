from __future__ import annotations

import os
from pathlib import Path

try:
    import webview
except ImportError as exc:
    raise SystemExit(
        "pywebview is required. Install it with: "
        "python -m pip install -r requirements-webui.txt"
    ) from exc

from web_backend import Bridge as CoreBridge
from web_backend_adofai import AdoFAIMixin


class Bridge(AdoFAIMixin, CoreBridge):
    """Web UI backend with advanced export/help APIs layered on the core editor bridge."""

    def get_adofai_export_defaults(self, selected_indices=None):
        defaults = super().get_adofai_export_defaults(selected_indices)
        defaults["selectedOnly"] = False
        return defaults


ROOT = Path(__file__).resolve().parent
DIST_INDEX = ROOT / "frontend" / "dist" / "index.html"


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
    window = webview.create_window(
        "AdopyHzEditor",
        _ui_url(),
        js_api=bridge,
        width=1440,
        height=860,
        min_size=(1040, 640),
        background_color="#20242a",
    )
    bridge.attach_window(window)
    webview.start(debug=os.environ.get("ADOPY_WEB_UI_DEBUG") == "1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
