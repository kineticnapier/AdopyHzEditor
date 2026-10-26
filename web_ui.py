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

from core.note_model import Note
from i18n import set_language
import web.backend as web_backend_module

from web.backend import Bridge as CoreBridge
from web.adofai import AdoFAIMixin
from web.presets import PresetMixin
from web.tools import ToolsMixin


class Bridge(PresetMixin, ToolsMixin, AdoFAIMixin, CoreBridge):
    """Web UI backend with export, workspace and utility APIs layered on the core editor bridge."""

    def __init__(self) -> None:
        super().__init__()
        self._status = "準備完了"

    def _curve_controls(self, p0: float, p3: float) -> tuple[float, float]:
        """Extend the Web UI's creation-time Bezier shape presets.

        Custom values are encoded in curveShape as ``custom:P1:P2`` where P1/P2
        are percentages along the pitch delta. This keeps project persistence
        backward-compatible because curveShape is already saved as a string.
        """
        start = float(p0)
        delta = float(p3) - start
        shape = str(self.settings.get("curveShape", "ease"))

        if shape == "sine":
            return start + delta * 0.12, start + delta * 0.88
        if shape == "expo_in":
            return start, start + delta * 0.05
        if shape == "expo_out":
            return start + delta * 0.95, start + delta
        if shape.startswith("custom:"):
            try:
                _, raw_p1, raw_p2 = shape.split(":", 2)
                p1 = max(-200.0, min(300.0, float(raw_p1))) / 100.0
                p2 = max(-200.0, min(300.0, float(raw_p2))) / 100.0
            except (TypeError, ValueError):
                p1, p2 = 0.0, 1.0
            return start + delta * p1, start + delta * p2

        return super()._curve_controls(p0, p3)

    def apply_curve_shape(self, indices):
        """Apply the current curve-shape preset to existing selected curves."""
        with self._lock:
            valid = sorted(
                {
                    int(i)
                    for i in indices
                    if 0 <= int(i) < len(self.notes) and self.notes[int(i)].is_curve
                }
            )
            if not valid:
                return {"notes": self._note_dicts(), "status": "カーブノートが選択されていません"}

            self._push_undo()
            for i in valid:
                n = self.notes[i].normalized()
                end_midi = float(n.midi_end if n.midi_end is not None else n.midi)
                c1, c2 = self._curve_controls(float(n.midi), end_midi)
                self.notes[i] = Note(
                    n.start,
                    n.end,
                    n.midi,
                    n.velocity,
                    "curve",
                    end_midi,
                    c1,
                    c2,
                    n.interpolation,
                    n.target_angle,
                ).normalized()

            self._dirty = True
            self._sync_notes_to_player()
            self._status = f"{len(valid)}個のカーブに形状を適用しました"
            return {"notes": self._note_dicts(), "status": self._status}

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
        defaults["angleCompressionMode"] = "auto"
        defaults["angleCompressionFixedAngle"] = 165.0
        defaults["songSourcePath"] = str(self.audio_path or "")
        return defaults

    def choose_adofai_song_source(self):
        path = self._dialog(webview.FileDialog.OPEN, file_types=web_backend_module.AUDIO_FILE_TYPES)
        if not path:
            return {"ok": False, "status": "キャンセルしました"}
        source = str(Path(path).resolve())
        return {
            "ok": True,
            "path": source,
            "name": Path(source).name,
            "status": f"音源先を {Path(source).name} に変更しました",
        }

    def _reserve_integer_terminal_tiles(self, notes, final_mode):
        """Let a distinct terminal-tile mode also apply to exact integer cycles.

        The exporter only enters its final-tile branch when ``frac > 0``. After
        integer-boundary stabilization an A note can be exactly 30 cycles, so a
        horizontal/custom/cardinal terminal setting would otherwise never run.
        Work only on export copies and reserve the final full cycle as an almost-
        full fractional cycle. The timing difference is below a nanosecond-scale
        cycle epsilon while tile count stays unchanged.
        """
        mode = str(final_mode or "scaled").lower().replace(" ", "_").replace("-", "_")
        if mode == "scaled":
            return

        eps = 1e-9
        for note in notes:
            n = note.normalized()
            if n.is_curve or n.duration <= 0 or n.freq <= 0:
                continue
            keycount = float(n.freq) * float(n.duration)
            nearest = int(round(keycount))
            if nearest <= 0 or abs(keycount - nearest) > 10.0 * eps:
                continue
            safe_keycount = float(nearest) - 2.0 * eps
            note.end = float(n.start) + safe_keycount / float(n.freq)

    def _prepare_adofai_export(self, raw_options, selected_indices):
        # Web UI no longer exposes just intonation. Force equal temperament here
        # as well so stale/front-end-crafted values cannot change the result.
        options = dict(raw_options or {})
        options["harmonyTuning"] = "equal temperament"
        notes, build_opts, workflow = super()._prepare_adofai_export(options, selected_indices)

        # The export song can be different from the audio used for analysis and
        # note editing. Keep the project audio untouched and override only the
        # ADOFAI songFilename/copy workflow.
        song_source = str(options.get("songSourcePath") or self.audio_path or "").strip()
        use_song = bool(options.get("useProjectSong", bool(song_source)))
        if use_song:
            if not song_source:
                raise ValueError("音源先を選択してください")
            build_opts["song_filename"] = Path(song_source).name
            if bool(options.get("songOffsetAuto", True)):
                build_opts["song_offset_ms"] = min((n.normalized().start for n in notes), default=0.0) * 1000.0
            else:
                try:
                    song_offset = float(options.get("songOffsetMs", 0.0))
                except (TypeError, ValueError):
                    song_offset = 0.0
                build_opts["song_offset_ms"] = max(-3600000.0, min(3600000.0, song_offset))
            workflow["songSourcePath"] = song_source
            workflow["copySong"] = bool(options.get("copyProjectSong", True))
        else:
            build_opts["song_filename"] = None
            build_opts["song_offset_ms"] = None
            workflow["songSourcePath"] = None
            workflow["copySong"] = False

        mode = str(options.get("angleCompressionMode", "auto"))
        if build_opts.get("method") == "rabbit_zip" and mode == "fixed":
            try:
                fixed_angle = float(options.get("angleCompressionFixedAngle", 165.0))
            except (TypeError, ValueError):
                fixed_angle = 165.0
            fixed_angle = max(0.001, min(359.999, fixed_angle))

            # Fixed Angle Compression controls only the full/main tiles. The
            # terminal tile remains governed by finalAngleMode, even if the note
            # lands on an exact integer cycle count. Keep target-BPM disabled
            # because it suppresses per-note target_angle inside the exporter.
            for note in notes:
                note.target_angle = fixed_angle
            self._reserve_integer_terminal_tiles(notes, build_opts.get("final_angle_mode", "scaled"))
            if build_opts.get("rabbit_x_mode") == "target_bpm":
                build_opts["rabbit_x_mode"] = "floor"

        return notes, build_opts, workflow


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


def _webview_gui() -> str | None:
    """Use the same Qt backend for Windows source and packaged runs.

    pywebview's EdgeChromium/WinForms file dialog is not marshaled to its GUI
    thread in 6.2.1.  Qt uses queued signals for dialogs and window operations.
    ADOPY_WEB_UI_GUI remains available for renderer diagnosis; ``auto`` restores
    pywebview's platform default.
    """
    override = os.environ.get("ADOPY_WEB_UI_GUI", "").strip().lower()
    if override in {"auto", "default"}:
        return None
    if override:
        return override
    if sys.platform.startswith("win"):
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
    window.events.closing += bridge.on_window_closing
    webview.start(
        gui=_webview_gui(),
        debug=os.environ.get("ADOPY_WEB_UI_DEBUG") == "1",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
