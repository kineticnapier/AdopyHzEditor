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

from i18n import set_language
import web.backend as web_backend_module
from web.audio import WebAudioPlayer, decode_audio_file as decode_audio_file_compat

# Keep the shared/PySide6 audio player untouched. The React Web backend was
# written against an older AudioPlayer-facing API, so install a small adapter
# only in the Web backend module before CoreBridge instances are created.
web_backend_module.AudioPlayer = WebAudioPlayer
web_backend_module.decode_audio_file = decode_audio_file_compat

from web.backend import Bridge as CoreBridge
from web.adofai import AdoFAIMixin
from web.presets import PresetMixin
from web.tools import ToolsMixin


class Bridge(PresetMixin, ToolsMixin, AdoFAIMixin, CoreBridge):
    """Web UI backend with export, workspace and utility APIs layered on the core editor bridge."""

    def __init__(self) -> None:
        super().__init__()
        self._status = "準備完了"

    def open_audio(self):
        super().open_audio()
        with self._lock:
            if self.audio_path:
                self._status = f"{Path(self.audio_path).name} を読み込みました"
        return self.get_state()

    def reanalyze_audio(self):
        had_audio = bool(self.audio_path)
        super().reanalyze_audio()
        with self._lock:
            self._status = "解析が完了しました" if had_audio else "先に音声を開いてください"
        return self.get_state()

    def get_adofai_export_defaults(self, selected_indices=None):
        defaults = super().get_adofai_export_defaults(selected_indices)
        defaults["selectedOnly"] = False
        defaults["harmonyTuning"] = "equal temperament"
        return defaults

    def _prepare_adofai_export(self, raw_options, selected_indices):
        # Web UI no longer exposes just intonation. Force equal temperament here
        # as well so stale/front-end-crafted values cannot change the result.
        options = dict(raw_options or {})
        options["harmonyTuning"] = "equal temperament"
        return super()._prepare_adofai_export(options, selected_indices)


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
    # The React/TypeScript shell is currently Japanese-only. Help text and other
    # Python-side translated strings should match it as well.
    set_language("ja", save=False)
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
