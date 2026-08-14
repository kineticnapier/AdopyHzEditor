from __future__ import annotations

import base64
import math
import threading
from pathlib import Path
from typing import Any

import numpy as np
import webview
from audio_analysis import (
    Spectrogram,
    analysis_profile_options,
    analyze_cqt,
    enhance_spectrogram,
)
from audio_player import AudioPlayer, decode_audio_file
from note_model import Note
from web_backend_io import IOMixin
from web_backend_notes import NoteMixin


AUDIO_FILE_TYPES = (
    "Audio Files (*.wav;*.mp3;*.ogg;*.flac;*.m4a;*.aac)",
    "All files (*.*)",
)
PROJECT_FILE_TYPES = (
    "AdopyHzEditor Project (*.adopyhz;*.ahe.json)",
    "JSON (*.json)",
    "All files (*.*)",
)
MIDI_FILE_TYPES = ("MIDI Files (*.mid;*.midi)", "All files (*.*)")
ADOF_FILE_TYPES = ("ADOFAI Level (*.adofai)", "All files (*.*)")


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(value)))


def _int_clamp(value: Any, lo: int, hi: int) -> int:
    return max(lo, min(hi, int(round(float(value)))))


class Bridge(NoteMixin, IOMixin):
    """Stateful Python backend for the React/TypeScript editor shell.

    pywebview executes exposed API calls in worker threads, so mutable editor
    state is protected by a lock. AudioPlayer has its own internal lock.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._window = None
        self.player = AudioPlayer()
        self.spectrogram: Spectrogram | None = None
        self.audio_path: str | None = None
        self.project_path: str | None = None
        self.notes: list[Note] = []
        self._undo_stack: list[list[dict[str, Any]]] = []
        self._redo_stack: list[list[dict[str, Any]]] = []
        self._clipboard: list[Note] = []
        self._busy = False
        self._status = "Ready"
        self._dirty = False

        self.duration = 60.0
        self.midi_min = 12
        self.midi_max = 120
        self.pitch_step = 1.0

        self.settings: dict[str, Any] = {
            "volume": 85,
            "speed": 1.0,
            "notePreview": True,
            "previewVolume": 20,
            "previewOctave": 0,
            "previewSound": "sine",
            "exportOctave": 0,
            "exportSemitone": 0,
            "gridEnabled": False,
            "metronomeEnabled": False,
            "bpm": 175.0,
            "offsetMs": 0.0,
            "metronomeVolume": 35,
            "snapEnabled": False,
            "snapDiv": 1,
            "contrast": 115,
            "gamma": 75,
            "enhance": True,
            "displayMode": "wavetone",
            "harmonics": "off",
            "colormap": "wavetone",
            "analysisProfile": "Normal",
            "cqtResolution": "profile default",
            "curveShape": "ease",
            "curveInterpolation": "bezier_pitch",
            "targetAngle": 165.0,
        }
        self.view: dict[str, Any] = {
            "mode": "spec",
            "start": 0.0,
            "windowSeconds": 12.0,
            "pitchBottom": 12,
            "visibleNotes": 60,
        }

        self.player.set_virtual_duration(self.duration)
        self._apply_player_settings()

    def attach_window(self, window) -> None:
        self._window = window

    # ------------------------------------------------------------------
    # State / serialization
    # ------------------------------------------------------------------
    def ping(self) -> dict[str, Any]:
        return {
            "ok": True,
            "app": "AdopyHzEditor",
            "ui": "React + TypeScript",
            "capabilities": [
                "audio",
                "playback",
                "spectrogram",
                "notes",
                "project",
                "midi",
                "adofai",
            ],
        }

    def _note_dicts(self) -> list[dict[str, Any]]:
        return [n.normalized().to_dict() for n in self.notes]

    def _playback_dict(self) -> dict[str, Any]:
        duration = max(float(self.duration), float(self.player.duration))
        return {
            "time": float(self.player.time),
            "duration": duration,
            "playing": bool(self.player.playing),
            "available": bool(self.player.available),
            "error": self.player.error,
        }

    def _state_dict(self) -> dict[str, Any]:
        return {
            "settings": dict(self.settings),
            "view": dict(self.view),
            "playback": self._playback_dict(),
            "audio": {
                "path": self.audio_path,
                "name": Path(self.audio_path).name if self.audio_path else None,
                "loaded": bool(self.audio_path),
            },
            "projectPath": self.project_path,
            "notes": self._note_dicts(),
            "analysis": {
                "available": self.spectrogram is not None,
                "duration": float(self.duration),
                "midiMin": int(self.midi_min),
                "midiMax": int(self.midi_max),
                "pitchStep": float(self.pitch_step),
            },
            "busy": bool(self._busy),
            "status": self._status,
            "dirty": bool(self._dirty),
        }

    def get_state(self) -> dict[str, Any]:
        with self._lock:
            return self._state_dict()

    def get_settings(self) -> dict[str, Any]:
        with self._lock:
            return dict(self.settings)

    def get_playback_state(self) -> dict[str, Any]:
        with self._lock:
            return self._playback_dict()

    # ------------------------------------------------------------------
    # Settings / view
    # ------------------------------------------------------------------
    def _normalize_setting(self, key: str, value: Any) -> Any:
        if key in {"volume", "previewVolume", "metronomeVolume"}:
            return _int_clamp(value, 0, 100)
        if key == "speed":
            return _clamp(value, 0.10, 4.0)
        if key == "previewOctave":
            return _int_clamp(value, -4, 4)
        if key == "exportOctave":
            return _int_clamp(value, -4, 4)
        if key == "exportSemitone":
            return _int_clamp(value, -12, 12)
        if key == "bpm":
            return _clamp(value, 1.0, 10000.0)
        if key == "offsetMs":
            return _clamp(value, -600000.0, 600000.0)
        if key == "snapDiv":
            return _int_clamp(value, 1, 64)
        if key == "contrast":
            return _int_clamp(value, 0, 300)
        if key == "gamma":
            return _int_clamp(value, 5, 500)
        if key == "targetAngle":
            return _clamp(value, 0.001, 359.999)
        if key in {"notePreview", "gridEnabled", "metronomeEnabled", "snapEnabled", "enhance"}:
            return bool(value)
        if key == "previewSound":
            text = str(value)
            return text if text in {"sine", "piano", "organ", "square", "triangle"} else "sine"
        if key == "displayMode":
            text = str(value)
            return text if text in {"wavetone", "ridge", "smooth"} else "wavetone"
        if key == "harmonics":
            text = str(value)
            return text if text in {"off", "soft", "strong"} else "off"
        if key == "colormap":
            text = str(value)
            return text if text in {"wavetone", "viridis", "magma", "inferno", "plasma", "gray"} else "wavetone"
        if key == "analysisProfile":
            text = str(value)
            return text if text in {"Fast", "Normal", "Precise", "Full C0-C10"} else "Normal"
        if key == "cqtResolution":
            text = str(value)
            allowed = {"profile default", "100 cents", "50 cents", "25 cents", "12.5 cents", "41 EDO", "53 EDO"}
            return text if text in allowed else "profile default"
        if key == "curveShape":
            text = str(value).lower().replace(" ", "_").replace("-", "_")
            return text if text in {"ease", "s_curve", "linear", "ease_in", "ease_out"} else "ease"
        if key == "curveInterpolation":
            text = str(value).lower().replace(" ", "_").replace("-", "_")
            return text if text in {"bezier_pitch", "linear_pitch", "linear_hz", "bezier_hz"} else "bezier_pitch"
        return value

    def update_settings(self, changes: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(changes, dict):
            raise TypeError("changes must be an object")
        with self._lock:
            for key, value in changes.items():
                if key in self.settings:
                    self.settings[key] = self._normalize_setting(key, value)
            self._apply_player_settings()
            self._dirty = True
            self._status = "Settings updated"
            return dict(self.settings)

    def _apply_player_settings(self) -> None:
        self.player.set_volume(float(self.settings["volume"]) / 100.0)
        self.player.set_playback_speed(float(self.settings["speed"]))
        self.player.set_note_sound(
            enabled=bool(self.settings["notePreview"]),
            volume=float(self.settings["previewVolume"]) / 100.0,
            octave_shift=int(self.settings["previewOctave"]),
            instrument=str(self.settings["previewSound"]),
        )
        self.player.set_metronome(
            enabled=bool(self.settings["metronomeEnabled"]),
            bpm=float(self.settings["bpm"]),
            offset_sec=float(self.settings["offsetMs"]) / 1000.0,
            volume=float(self.settings["metronomeVolume"]) / 100.0,
        )

    def set_view(self, changes: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(changes, dict):
            raise TypeError("changes must be an object")
        with self._lock:
            mode = str(changes.get("mode", self.view["mode"]))
            if mode in {"spec", "notes", "both"}:
                self.view["mode"] = mode

            window = _clamp(changes.get("windowSeconds", self.view["windowSeconds"]), 0.2, max(0.2, self.duration))
            start = _clamp(changes.get("start", self.view["start"]), 0.0, max(0.0, self.duration - window))
            visible = _int_clamp(changes.get("visibleNotes", self.view["visibleNotes"]), 6, max(6, self.midi_max - self.midi_min + 1))
            max_bottom = max(self.midi_min, self.midi_max - visible + 1)
            bottom = _int_clamp(changes.get("pitchBottom", self.view["pitchBottom"]), self.midi_min, max_bottom)
            self.view.update(
                start=start,
                windowSeconds=window,
                pitchBottom=bottom,
                visibleNotes=visible,
            )
            return dict(self.view)

    def fit_view(self) -> dict[str, Any]:
        with self._lock:
            self.view.update(
                start=0.0,
                windowSeconds=max(0.2, float(self.duration)),
                pitchBottom=int(self.midi_min),
                visibleNotes=max(6, int(self.midi_max - self.midi_min + 1)),
            )
            return dict(self.view)

    # ------------------------------------------------------------------
    # Audio / analysis / playback
    # ------------------------------------------------------------------
    def _dialog(self, dialog_type, *, file_types=(), save_filename: str = "") -> str | None:
        window = self._window or webview.active_window()
        if window is None:
            return None
        result = window.create_file_dialog(
            dialog_type,
            allow_multiple=False,
            save_filename=save_filename,
            file_types=file_types,
        )
        if not result:
            return None
        return str(result[0])

    def _resolution_options(self, profile: str, resolution: str) -> dict[str, Any]:
        options = dict(analysis_profile_options(profile))
        resolution = str(resolution)
        if resolution == "profile default":
            return options

        bins_per_octave = {
            "100 cents": 12,
            "50 cents": 24,
            "25 cents": 48,
            "12.5 cents": 96,
            "41 EDO": 41,
            "53 EDO": 53,
        }.get(resolution)
        if bins_per_octave is not None:
            options["cqt_bins_per_octave"] = bins_per_octave
            options["fold_to_semitone"] = False
        return options

    def _analyze_path(self, path: str) -> Spectrogram:
        with self._lock:
            profile = str(self.settings["analysisProfile"])
            resolution = str(self.settings["cqtResolution"])
        options = self._resolution_options(profile, resolution)
        return analyze_cqt(path, use_cache=True, **options)

    def _install_spectrogram(self, spec: Spectrogram) -> None:
        self.spectrogram = spec
        self.duration = max(0.001, float(spec.duration))
        self.midi_min = int(spec.midi_min)
        self.midi_max = int(spec.midi_max)
        self.pitch_step = max(1e-6, float(getattr(spec, "pitch_step", 1.0) or 1.0))
        self.view["windowSeconds"] = min(float(self.view["windowSeconds"]), self.duration)
        self.view["start"] = _clamp(self.view["start"], 0.0, max(0.0, self.duration - self.view["windowSeconds"]))
        self.view["visibleNotes"] = min(int(self.view["visibleNotes"]), self.midi_max - self.midi_min + 1)
        max_bottom = max(self.midi_min, self.midi_max - int(self.view["visibleNotes"]) + 1)
        self.view["pitchBottom"] = _int_clamp(self.view["pitchBottom"], self.midi_min, max_bottom)
        self.player.set_virtual_duration(self.duration)

    def _load_audio_path(self, path: str, *, analyze: bool = True) -> None:
        abs_path = str(Path(path).resolve())
        audio, sr = decode_audio_file(abs_path, sr=44100)
        self.player.set_audio(audio, sr)
        spec = self._analyze_path(abs_path) if analyze else None
        with self._lock:
            self.audio_path = abs_path
            self.player.seek(0.0)
            if spec is not None:
                self._install_spectrogram(spec)
            else:
                self.duration = max(0.001, self.player.duration)
                self.player.set_virtual_duration(self.duration)
            self._sync_notes_to_player()
            self._status = f"Loaded {Path(abs_path).name}"

    def open_audio(self) -> dict[str, Any]:
        path = self._dialog(webview.FileDialog.OPEN, file_types=AUDIO_FILE_TYPES)
        if not path:
            return self.get_state()
        with self._lock:
            self._busy = True
            self._status = f"Loading {Path(path).name}..."
        try:
            self._load_audio_path(path, analyze=True)
        except Exception as exc:
            with self._lock:
                self._status = f"Audio load failed: {exc!r}"
            raise
        finally:
            with self._lock:
                self._busy = False
        return self.get_state()

    def reanalyze_audio(self) -> dict[str, Any]:
        with self._lock:
            path = self.audio_path
            if not path:
                self._status = "Open audio first"
                return self._state_dict()
            self._busy = True
            self._status = "Analyzing audio..."
        try:
            spec = self._analyze_path(path)
            with self._lock:
                self._install_spectrogram(spec)
                self._status = "Analysis ready"
        finally:
            with self._lock:
                self._busy = False
        return self.get_state()

    def get_spectrogram(self, max_columns: int = 1400) -> dict[str, Any]:
        with self._lock:
            spec = self.spectrogram
            settings = dict(self.settings)
        if spec is None:
            return {"available": False}

        z = enhance_spectrogram(
            spec.db,
            contrast=float(settings["contrast"]) / 100.0,
            gamma=float(settings["gamma"]) / 100.0,
            per_bin=bool(settings["enhance"]),
            harmonic_mode=str(settings["harmonics"]),
            display_mode=str(settings["displayMode"]),
        ).astype(np.float32, copy=False)
        z = np.clip(z, 0.0, 1.0)

        cols = z.shape[1]
        target = max(64, min(4096, int(max_columns)))
        if cols > target:
            edges = np.linspace(0, cols, target + 1, dtype=np.int64)
            reduced = np.empty((z.shape[0], target), dtype=np.float32)
            for i in range(target):
                a = int(edges[i])
                b = max(a + 1, int(edges[i + 1]))
                reduced[:, i] = np.max(z[:, a:b], axis=1)
            z = reduced

        pixels = np.ascontiguousarray(np.rint(z * 255.0).astype(np.uint8))
        return {
            "available": True,
            "rows": int(pixels.shape[0]),
            "cols": int(pixels.shape[1]),
            "data": base64.b64encode(pixels.tobytes()).decode("ascii"),
            "duration": float(spec.duration),
            "midiMin": int(spec.midi_min),
            "midiMax": int(spec.midi_max),
            "pitchStep": float(getattr(spec, "pitch_step", 1.0) or 1.0),
        }

    def toggle_playback(self) -> dict[str, Any]:
        with self._lock:
            self._sync_notes_to_player()
            if not self.player.available:
                self._status = f"Playback unavailable: {self.player.error}"
                return self._playback_dict()
            self.player.toggle()
            self._status = "Playing" if self.player.playing else "Paused"
            return self._playback_dict()

    def stop_playback(self) -> dict[str, Any]:
        with self._lock:
            self.player.stop()
            self._status = "Stopped"
            return self._playback_dict()

    def seek_to(self, seconds: float) -> dict[str, Any]:
        with self._lock:
            target = _clamp(seconds, 0.0, max(0.0, self.duration))
            self.player.seek(target)
            return self._playback_dict()

    def seek_relative(self, seconds: float) -> dict[str, Any]:
        return self.seek_to(float(self.player.time) + float(seconds))
