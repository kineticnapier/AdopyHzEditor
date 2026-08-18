from __future__ import annotations

import os
import sys
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

# The Web backend still uses the older analysis-facing contract in a few
# places. Adapt it to core.audio_analysis without changing the shared API.
_core_analyze_cqt = web_backend_module.analyze_cqt
_core_enhance_spectrogram = web_backend_module.enhance_spectrogram


def _analyze_cqt_compat(audio_path, *, profile="Normal", resolution="profile default", **kwargs):
    options = web_backend_module.analysis_profile_options(str(profile))
    resolution_bins = {
        "100 cents": 12,
        "50 cents": 24,
        "25 cents": 48,
        "12.5 cents": 96,
        "41 EDO": 41,
        "53 EDO": 53,
    }.get(str(resolution))
    if resolution_bins is not None:
        options["cqt_bins_per_octave"] = resolution_bins
        options["fold_to_semitone"] = False
    options.update(kwargs)
    return _core_analyze_cqt(audio_path, **options)


def _enhance_spectrogram_compat(
    data,
    *,
    contrast=0.72,
    gamma=0.75,
    enhance=True,
    display_mode="smooth",
    harmonics="off",
    **kwargs,
):
    return _core_enhance_spectrogram(
        data,
        contrast=contrast,
        gamma=gamma,
        per_bin=bool(enhance),
        display_mode=display_mode,
        harmonic_mode=harmonics,
        **kwargs,
    )


web_backend_module.analyze_cqt = _analyze_cqt_compat
web_backend_module.enhance_spectrogram = _enhance_spectrogram_compat

# Spectrogram used to expose its dB matrix as .data. Keep the Web backend's
# existing read path working while core uses the clearer .db field.
if not hasattr(web_backend_module.Spectrogram, "data"):
    web_backend_module.Spectrogram.data = property(lambda self: self.db)

from web.backend import Bridge as CoreBridge
from web.adofai import AdoFAIMixin
from web.presets import PresetMixin
from web.tools import ToolsMixin


class Bridge(PresetMixin, ToolsMixin, AdoFAIMixin, CoreBridge):
    """Web UI backend with export, workspace and utility APIs layered on the core editor bridge."""

    def __init__(self) -> None:
        super().__init__()
        self._status = "準備完了"

    # IOMixin was written against these helper names before the Web backend
    # consolidation. Keep them here until that mixin is rewritten directly
    # against CoreBridge's current helpers.
    def _dialog(self, mode, *, file_types, save_filename=None):
        paths = self._file_dialog(
            mode,
            file_types=file_types,
            allow_multiple=False,
            save_filename=save_filename,
        )
        return str(paths[0]) if paths else None

    def _state_dict(self):
        return self.get_state()

    def _load_audio_path(self, path, *, analyze=True):
        decoded = decode_audio_file_compat(path)
        with self._lock:
            self._set_audio_data(str(path), decoded)
        if analyze:
            self._analyze_current_audio()
        return self.get_state()

    def _normalize_setting(self, key, value):
        if key in {"volume", "previewVolume", "metronomeVolume"}:
            return max(0, min(100, int(round(float(value)))))
        if key == "speed":
            return max(0.1, min(4.0, float(value)))
        if key in {"previewOctave", "exportOctave"}:
            return max(-4, min(4, int(round(float(value)))))
        if key == "exportSemitone":
            return max(-12, min(12, int(round(float(value)))))
        if key == "bpm":
            return max(1.0, min(10000.0, float(value)))
        if key == "offsetMs":
            return max(-600000.0, min(600000.0, float(value)))
        if key == "snapDiv":
            return max(1, min(64, int(round(float(value)))))
        if key == "contrast":
            return max(0, min(300, int(round(float(value)))))
        if key == "gamma":
            return max(5, min(500, int(round(float(value)))))
        if key == "targetAngle":
            return max(0.001, min(359.999, float(value)))
        if key in {"notePreview", "gridEnabled", "metronomeEnabled", "snapEnabled", "enhance"}:
            return bool(value)
        return str(value)

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


# In a PyInstaller build, bundled data lives under sys._MEIPASS. In a source
# checkout, keep using the repository root next to this file.
ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
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


def _packaged_gui() -> str | None:
    """Avoid pythonnet/WinForms in the frozen Windows package.

    pythonnet's .NET Framework loader has known failure modes after freezing
    where Python.Runtime.dll is present but Loader.Initialize cannot be resolved.
    The packaged Windows build therefore uses pywebview's Qt/PySide6 backend.
    Source/dev runs keep pywebview's normal platform selection.
    """
    if sys.platform.startswith("win") and getattr(sys, "frozen", False):
        return "qt"
    return None


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
    webview.start(
        gui=_packaged_gui(),
        debug=os.environ.get("ADOPY_WEB_UI_DEBUG") == "1",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
