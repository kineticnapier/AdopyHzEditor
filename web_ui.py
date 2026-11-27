from __future__ import annotations

import json
import math
import os
import sys
import threading
import time
from pathlib import Path

try:
    import webview
except ImportError as exc:
    raise SystemExit(
        "pywebview is required. Install it with: "
        "python -m pip install -r requirements-webui.txt"
    ) from exc

from core.note_model import Note
from i18n import language_config_path, set_language, system_default_language, tr
import web.backend as web_backend_module

from web.backend import Bridge as CoreBridge
from web.adofai import AdoFAIMixin
from web.preferences import PreferencesMixin
from web.presets import PresetMixin
from web.tools import ToolsMixin


class Bridge(PreferencesMixin, PresetMixin, ToolsMixin, AdoFAIMixin, CoreBridge):
    """Web UI backend with export, workspace and utility APIs layered on the core editor bridge."""

    def __init__(self) -> None:
        super().__init__()
        self._status = tr("msg.ready")

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
                raw1, raw2 = float(raw_p1), float(raw_p2)
                if not (math.isfinite(raw1) and math.isfinite(raw2)):
                    raise ValueError("custom curve controls must be finite")
                p1 = max(-200.0, min(300.0, raw1)) / 100.0
                p2 = max(-200.0, min(300.0, raw2)) / 100.0
            except (TypeError, ValueError):
                p1, p2 = 0.0, 1.0
            return start + delta * p1, start + delta * p2

        return super()._curve_controls(p0, p3)

    def apply_curve_shape(self, indices):
        """Apply the current curve-shape preset to existing selected curves."""
        with self._lock:
            valid = [i for i in self._valid_indices(indices) if self.notes[i].is_curve]
            if not valid:
                return {"notes": self._note_dicts(), "changed": False, "status": tr("msg.no_curve_selection")}

            # Validate and prepare every note before changing history or notes.
            updated: list[tuple[int, Note]] = []
            for i in valid:
                n = self.notes[i].normalized()
                end_midi = float(n.midi_end if n.midi_end is not None else n.midi)
                c1, c2 = self._curve_controls(float(n.midi), end_midi)
                updated.append((i, Note(
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
                ).normalized()))

            if all(self.notes[i] == note for i, note in updated):
                self._status = tr("msg.shape_unchanged")
                return {"notes": self._note_dicts(), "changed": False, "dirty": self._dirty, "status": self._status}

            self._push_undo()
            for i, note in updated:
                self.notes[i] = note
            self._dirty = True
            self._sync_notes_to_player()
            self._status = tr("msg.shape_applied", count=len(valid))
            return {"notes": self._note_dicts(), "changed": True, "dirty": self._dirty, "status": self._status}

    def open_audio(self):
        super().open_audio()
        with self._lock:
            if self.audio_path:
                self._status = tr("msg.audio_loaded", name=Path(self.audio_path).name)
        return self.get_state()

    def reanalyze_audio(self):
        had_audio = bool(self.audio_path)
        super().reanalyze_audio()
        with self._lock:
            self._status = tr("msg.analysis_done") if had_audio else tr("msg.open_audio_before")
        return self.get_state()

    def get_adofai_export_defaults(self, selected_indices=None, selected_only=False):
        # Keep the Web bridge signature in sync with AdoFAIMixin. Otherwise
        # the dialog's initial export scope cannot reach offset calculation.
        defaults = super().get_adofai_export_defaults(selected_indices, selected_only)
        defaults["harmonyTuning"] = "equal temperament"
        defaults["angleCompressionMode"] = "auto"
        defaults["angleCompressionFixedAngle"] = 165.0
        defaults["songSourcePath"] = str(self.audio_path or "")
        return self._saved_adofai_export_defaults(defaults)

    def choose_adofai_song_source(self):
        path = self._dialog(webview.FileDialog.OPEN, file_types=web_backend_module.AUDIO_FILE_TYPES)
        if not path:
            return {"ok": False, "status": tr("msg.cancelled")}
        source = str(Path(path).resolve())
        return {
            "ok": True,
            "path": source,
            "name": Path(source).name,
            "status": tr("msg.song_source_changed", name=Path(source).name),
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
                raise ValueError(tr("msg.select_song_source"))
            build_opts["song_filename"] = Path(song_source).name
            if bool(options.get("songOffsetAuto", True)):
                build_opts["song_offset_ms"] = min((n.normalized().start for n in notes), default=0.0) * 1000.0
            else:
                try:
                    song_offset = float(options.get("songOffsetMs", 0.0))
                except (TypeError, ValueError):
                    song_offset = 0.0
                if not math.isfinite(song_offset):
                    raise ValueError(tr("msg.song_offset_finite"))
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
            if not math.isfinite(fixed_angle):
                raise ValueError(tr("msg.fixed_angle_finite"))
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


# After the main window has closed, the process must end even if something is
# stuck: pywebview runs each JS API call on a non-daemon thread and, on Qt,
# returns its result with an evaluate_js that waits without a timeout, so a
# call caught by the close can keep Python alive with no window.
EXIT_GRACE_SECONDS = 5.0
_exit_watchdog_started = threading.Event()


def _start_exit_watchdog(grace: float = EXIT_GRACE_SECONDS, exit_fn=os._exit, stop=None) -> threading.Thread | None:
    """End the process ``grace`` seconds from now unless it ends first."""
    if _exit_watchdog_started.is_set():
        return None
    _exit_watchdog_started.set()

    def watchdog() -> None:
        deadline = time.monotonic() + grace
        while time.monotonic() < deadline:
            if stop is not None and stop.is_set():
                return
            time.sleep(0.05)
        if stop is not None and stop.is_set():
            return
        try:
            sys.stdout.flush()
            sys.stderr.flush()
        finally:
            exit_fn(0)

    thread = threading.Thread(target=watchdog, name="adopyhz-exit-watchdog", daemon=True)
    thread.start()
    return thread


def _quiet_qt_environment() -> None:
    """Turn off Qt's DXGI vblank thread before the QApplication exists.

    Qt starts a QDxgiVSyncService on Windows for Qt Quick frame pacing; this
    app draws through WebEngine, so it is not needed, and at shutdown it
    prints "QDxgiVSyncService not destroyed in time" into the console.
    A value the user set is kept.
    """
    os.environ.setdefault("QT_D3D_NO_VBLANK_THREAD", "1")


def _saved_language() -> str | None:
    try:
        data = json.loads(language_config_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    language = data.get("language") if isinstance(data, dict) else None
    return str(language) if language else None


def main() -> int:
    _quiet_qt_environment()
    # The language picked in 環境設定, or on first launch Windows' own; the
    # screens get the same language from apply_startup_preferences.
    set_language(_saved_language() or system_default_language(), save=False)
    bridge = Bridge()
    bridge._preferences_file = language_config_path()
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
    window.events.closed += lambda *_args: _start_exit_watchdog()
    webview.start(
        gui=_webview_gui(),
        debug=os.environ.get("ADOPY_WEB_UI_DEBUG") == "1",
    )
    # Also covers a loop that ends without a closed event.
    _start_exit_watchdog()
    try:
        bridge.player.stop()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
