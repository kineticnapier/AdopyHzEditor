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
from web_backend_editing import EditingMixin
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


class Bridge(EditingMixin, NoteMixin, IOMixin):
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
                "spectrogram",
                "notes",
                "playback",
                "project",
                "midi",
                "adofai",
            ],
        }

    def _note_dicts(self) -> list[dict[str, Any]]:
        return [n.normalized().to_dict() for n in self.notes]

    def _analysis_state(self) -> dict[str, Any]:
        if self.spectrogram is None:
            return {
                "available": False,
                "duration": float(self.duration),
                "midiMin": int(self.midi_min),
                "midiMax": int(self.midi_max),
                "pitchStep": float(self.pitch_step),
            }
        return {
            "available": True,
            "duration": float(self.spectrogram.duration),
            "midiMin": int(self.spectrogram.midi_min),
            "midiMax": int(self.spectrogram.midi_max),
            "pitchStep": float(self.spectrogram.pitch_step),
        }

    def get_state(self) -> dict[str, Any]:
        with self._lock:
            playback = self.get_playback_state()
            return {
                "settings": dict(self.settings),
                "view": dict(self.view),
                "playback": playback,
                "audio": {
                    "path": self.audio_path,
                    "name": Path(self.audio_path).name if self.audio_path else None,
                    "loaded": bool(self.audio_path),
                },
                "projectPath": self.project_path,
                "notes": self._note_dicts(),
                "analysis": self._analysis_state(),
                "busy": bool(self._busy),
                "status": self._status,
                "dirty": bool(self._dirty),
            }

    def get_settings(self) -> dict[str, Any]:
        with self._lock:
            return dict(self.settings)

    def update_settings(self, changes: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(changes, dict):
            raise TypeError("changes must be an object")
        with self._lock:
            for key, value in changes.items():
                if key not in self.settings:
                    continue
                if key in {"volume", "previewVolume", "metronomeVolume"}:
                    self.settings[key] = _int_clamp(value, 0, 100)
                elif key == "speed":
                    self.settings[key] = _clamp(value, 0.1, 4.0)
                elif key in {"previewOctave", "exportOctave"}:
                    self.settings[key] = _int_clamp(value, -4, 4)
                elif key == "exportSemitone":
                    self.settings[key] = _int_clamp(value, -12, 12)
                elif key == "bpm":
                    self.settings[key] = _clamp(value, 1.0, 10000.0)
                elif key == "offsetMs":
                    self.settings[key] = _clamp(value, -600000.0, 600000.0)
                elif key == "snapDiv":
                    self.settings[key] = _int_clamp(value, 1, 64)
                elif key == "contrast":
                    self.settings[key] = _int_clamp(value, 0, 300)
                elif key == "gamma":
                    self.settings[key] = _int_clamp(value, 5, 500)
                elif key == "targetAngle":
                    self.settings[key] = _clamp(value, 0.001, 359.999)
                elif key in {"notePreview", "gridEnabled", "metronomeEnabled", "snapEnabled", "enhance"}:
                    self.settings[key] = bool(value)
                else:
                    self.settings[key] = str(value)
            self._apply_player_settings()
            self._dirty = True
            return dict(self.settings)

    def _apply_player_settings(self) -> None:
        self.player.set_volume(float(self.settings["volume"]) / 100.0)
        self.player.set_speed(float(self.settings["speed"]))
        self.player.configure_preview(
            enabled=bool(self.settings["notePreview"]),
            volume=float(self.settings["previewVolume"]) / 100.0,
            octave=int(self.settings["previewOctave"]),
            sound=str(self.settings["previewSound"]),
        )
        self.player.configure_metronome(
            enabled=bool(self.settings["metronomeEnabled"]),
            bpm=float(self.settings["bpm"]),
            offset_seconds=float(self.settings["offsetMs"]) / 1000.0,
            volume=float(self.settings["metronomeVolume"]) / 100.0,
        )

    # ------------------------------------------------------------------
    # View
    # ------------------------------------------------------------------
    def set_view(self, changes: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(changes, dict):
            raise TypeError("changes must be an object")
        with self._lock:
            if "mode" in changes and str(changes["mode"]) in {"spec", "notes", "both"}:
                self.view["mode"] = str(changes["mode"])
            if "windowSeconds" in changes:
                self.view["windowSeconds"] = _clamp(changes["windowSeconds"], 0.2, max(0.2, self.duration))
            if "start" in changes:
                max_start = max(0.0, self.duration - float(self.view["windowSeconds"]))
                self.view["start"] = _clamp(changes["start"], 0.0, max_start)
            if "pitchBottom" in changes:
                self.view["pitchBottom"] = _int_clamp(changes["pitchBottom"], 0, 127)
            if "visibleNotes" in changes:
                self.view["visibleNotes"] = _int_clamp(changes["visibleNotes"], 6, 128)
            return dict(self.view)

    def fit_view(self) -> dict[str, Any]:
        with self._lock:
            if self.notes:
                lo = min(n.pitch_bounds[0] for n in self.notes)
                hi = max(n.pitch_bounds[1] for n in self.notes)
                start = min(n.start for n in self.notes)
                end = max(n.end for n in self.notes)
                self.view["start"] = max(0.0, start - 0.25)
                self.view["windowSeconds"] = max(0.2, min(self.duration, end - self.view["start"] + 0.5))
                self.view["pitchBottom"] = max(0, int(math.floor(lo)) - 2)
                self.view["visibleNotes"] = max(6, min(128, int(math.ceil(hi - self.view["pitchBottom"])) + 3))
            else:
                self.view["start"] = 0.0
                self.view["windowSeconds"] = min(12.0, max(0.2, self.duration))
            return dict(self.view)

    # ------------------------------------------------------------------
    # Audio / analysis
    # ------------------------------------------------------------------
    def _set_audio_data(self, path: str, decoded) -> None:
        self.audio_path = str(path)
        self.player.set_audio(decoded.samples, decoded.sample_rate, path=str(path))
        self.duration = max(0.001, float(decoded.duration))
        self.player.set_virtual_duration(self.duration)
        self.view["start"] = 0.0
        self.view["windowSeconds"] = min(max(0.2, self.view["windowSeconds"]), self.duration)

    def open_audio(self) -> dict[str, Any]:
        paths = self._file_dialog(webview.OPEN_DIALOG, file_types=AUDIO_FILE_TYPES, allow_multiple=False)
        if not paths:
            return self.get_state()
        path = str(paths[0])
        self._busy = True
        self._status = f"Loading {Path(path).name}..."
        try:
            decoded = decode_audio_file(path)
            with self._lock:
                self._set_audio_data(path, decoded)
            self._analyze_current_audio()
            with self._lock:
                self._status = f"Loaded {Path(path).name}"
                self._dirty = False
            return self.get_state()
        finally:
            self._busy = False

    def _analyze_current_audio(self) -> None:
        if not self.audio_path:
            return
        self._busy = True
        profile = str(self.settings["analysisProfile"])
        resolution = str(self.settings["cqtResolution"])
        try:
            spec = analyze_cqt(
                self.audio_path,
                profile=profile,
                resolution=resolution,
            )
            with self._lock:
                self.spectrogram = spec
                self.duration = max(0.001, float(spec.duration))
                self.midi_min = int(spec.midi_min)
                self.midi_max = int(spec.midi_max)
                self.pitch_step = float(spec.pitch_step)
                self.player.set_virtual_duration(self.duration)
                self._status = "Analysis ready"
        finally:
            self._busy = False

    def reanalyze_audio(self) -> dict[str, Any]:
        if not self.audio_path:
            with self._lock:
                self._status = "Open an audio file first"
            return self.get_state()
        self._analyze_current_audio()
        return self.get_state()

    def get_spectrogram(self, max_columns: int = 1600) -> dict[str, Any]:
        with self._lock:
            spec = self.spectrogram
            if spec is None:
                return {"available": False}
            data = np.asarray(spec.data, dtype=np.float32)
            rows, cols = data.shape
            max_columns = max(64, min(4096, int(max_columns)))
            if cols > max_columns:
                edges = np.linspace(0, cols, max_columns + 1, dtype=np.int32)
                reduced = np.empty((rows, max_columns), dtype=np.float32)
                for i in range(max_columns):
                    a, b = int(edges[i]), int(edges[i + 1])
                    if b <= a:
                        b = min(cols, a + 1)
                    reduced[:, i] = np.max(data[:, a:b], axis=1)
                data = reduced
                cols = max_columns

            enhanced = enhance_spectrogram(
                data,
                contrast=float(self.settings["contrast"]) / 100.0,
                gamma=float(self.settings["gamma"]) / 100.0,
                enhance=bool(self.settings["enhance"]),
                display_mode=str(self.settings["displayMode"]),
                harmonics=str(self.settings["harmonics"]),
            )
            lo = float(np.min(enhanced)) if enhanced.size else 0.0
            hi = float(np.max(enhanced)) if enhanced.size else 1.0
            if hi <= lo + 1e-12:
                u8 = np.zeros_like(enhanced, dtype=np.uint8)
            else:
                u8 = np.clip((enhanced - lo) / (hi - lo) * 255.0, 0, 255).astype(np.uint8)
            return {
                "available": True,
                "rows": int(u8.shape[0]),
                "cols": int(u8.shape[1]),
                "data": base64.b64encode(u8.tobytes(order="C")).decode("ascii"),
                "duration": float(spec.duration),
                "midiMin": int(spec.midi_min),
                "midiMax": int(spec.midi_max),
                "pitchStep": float(spec.pitch_step),
            }

    # ------------------------------------------------------------------
    # Playback
    # ------------------------------------------------------------------
    def get_playback_state(self) -> dict[str, Any]:
        state = self.player.snapshot()
        return {
            "time": float(state.position),
            "duration": float(max(self.duration, state.duration, 0.001)),
            "playing": bool(state.playing),
            "available": bool(state.audio_loaded or self.duration > 0),
            "error": state.error,
        }

    def toggle_playback(self) -> dict[str, Any]:
        self.player.toggle()
        return self.get_playback_state()

    def stop_playback(self) -> dict[str, Any]:
        self.player.stop(reset=True)
        return self.get_playback_state()

    def seek_to(self, seconds: float) -> dict[str, Any]:
        self.player.seek(_clamp(seconds, 0.0, self.duration))
        return self.get_playback_state()

    def seek_relative(self, seconds: float) -> dict[str, Any]:
        current = self.player.snapshot().position
        return self.seek_to(current + float(seconds))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _file_dialog(self, mode, *, file_types, allow_multiple: bool = False, save_filename: str | None = None):
        if self._window is None:
            return []
        result = self._window.create_file_dialog(
            mode,
            allow_multiple=allow_multiple,
            file_types=file_types,
            save_filename=save_filename,
        )
        if result is None:
            return []
        if isinstance(result, str):
            return [result]
        return list(result)
