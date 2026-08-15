from __future__ import annotations

import math
from fractions import Fraction
from pathlib import Path
from typing import Any

import webview

from exporters.midi import export_midi
from i18n import available_languages, current_language, set_language, tr
from core.note_model import Note
from core.project_io import load_project
from tools.quick_hz import (
    AppendGeneratedDataToChart,
    CalculateHzInfo,
    GenerateOutputText,
    ReadChartTailFloor,
    ResolveGenerateCount,
    SaveChartAs,
)

PROJECT_FILE_TYPES = (
    "AdopyHzEditor Project (*.adopyhz;*.ahe.json)",
    "JSON (*.json)",
    "All files (*.*)",
)
MIDI_FILE_TYPES = ("MIDI Files (*.mid;*.midi)", "All files (*.*)")
ADOF_FILE_TYPES = ("ADOFAI Level (*.adofai)", "All files (*.*)")


class ToolsMixin:
    """Workspace, project-composition and utility APIs for the web UI."""

    # ------------------------------------------------------------------
    # Blank workspace / project composition
    # ------------------------------------------------------------------
    def get_blank_workspace_defaults(self) -> dict[str, Any]:
        with self._lock:
            return {
                "duration": max(1.0, float(self.duration)),
                "midiMin": int(self.midi_min),
                "midiMax": int(self.midi_max),
            }

    def apply_blank_workspace(self, options: dict[str, Any]) -> dict[str, Any]:
        duration = max(1.0, min(36000.0, float(options.get("duration", self.duration))))
        midi_min = max(0, min(127, int(options.get("midiMin", self.midi_min))))
        midi_max = max(0, min(127, int(options.get("midiMax", self.midi_max))))
        if midi_max <= midi_min:
            midi_max = min(127, midi_min + 12)
            if midi_max <= midi_min:
                midi_min = max(0, midi_max - 12)

        with self._lock:
            self.player.stop()
            self.player.clear_audio()
            self.audio_path = None
            self.spectrogram = None
            self.duration = duration
            self.midi_min = midi_min
            self.midi_max = midi_max
            self.pitch_step = 1.0
            self.view.update(
                start=0.0,
                windowSeconds=min(12.0, duration),
                pitchBottom=midi_min,
                visibleNotes=min(60, midi_max - midi_min + 1),
            )
            self.player.set_virtual_duration(max(duration, max((n.end for n in self.notes), default=0.0)))
            self.player.seek(0.0)
            self._sync_notes_to_player()
            self._dirty = True
            self._status = f"Blank workspace: {duration:.3f}s / MIDI {midi_min}-{midi_max}"
            return self._state_dict()

    def load_project_notes_only_dialog(self) -> dict[str, Any]:
        path = self._dialog(webview.FileDialog.OPEN, file_types=PROJECT_FILE_TYPES)
        if not path:
            return self.get_state()
        _audio, notes, settings = load_project(path)
        with self._lock:
            self.notes = [n.normalized() for n in notes]
            self._undo_stack.clear()
            self._redo_stack.clear()
            self._apply_project_settings(settings)
            self.project_path = str(Path(path).resolve())
            self.audio_path = None
            self.spectrogram = None
            self.player.clear_audio()
            self._fit_blank_bounds_to_notes()
            self._sync_notes_to_player()
            self._dirty = False
            self._status = f"Loaded notes only: {Path(path).name}"
            return self._state_dict()

    def merge_project_notes_dialog(self) -> dict[str, Any]:
        path = self._dialog(webview.FileDialog.OPEN, file_types=PROJECT_FILE_TYPES)
        if not path:
            return self.get_state()
        _audio, notes, _settings = load_project(path)
        if not notes:
            with self._lock:
                self._status = f"No notes in {Path(path).name}"
                return self._state_dict()
        with self._lock:
            self._push_undo()
            self.notes = sorted(
                [n.normalized() for n in self.notes] + [n.normalized() for n in notes],
                key=lambda n: (n.start, n.midi, n.end),
            )
            if self.audio_path is None or self.spectrogram is None:
                self._fit_blank_bounds_to_notes()
            self._sync_notes_to_player()
            self._dirty = True
            self._status = f"Merged {len(notes)} note(s) from {Path(path).name}"
            return self._state_dict()

    def _fit_blank_bounds_to_notes(self) -> None:
        if self.notes:
            pitches: list[float] = []
            for note in self.notes:
                n = note.normalized()
                pitches.extend(x for x in (n.midi, n.midi_end, n.ctrl1_midi, n.ctrl2_midi) if x is not None)
            self.duration = max(12.0, max(n.end for n in self.notes) + 2.0)
            if pitches:
                self.midi_min = min(12, max(0, int(math.floor(min(pitches))) - 12))
                self.midi_max = max(120, min(127, int(math.ceil(max(pitches))) + 12))
        else:
            self.duration = max(1.0, float(self.duration))
            self.midi_min = max(0, min(127, int(self.midi_min)))
            self.midi_max = max(self.midi_min + 1, min(127, int(self.midi_max)))
        visible = min(60, self.midi_max - self.midi_min + 1)
        self.view.update(start=0.0, windowSeconds=min(12.0, self.duration), pitchBottom=self.midi_min, visibleNotes=visible)
        self.player.set_virtual_duration(self.duration)

    def export_selected_midi_dialog(self, indices: list[int]) -> dict[str, Any]:
        valid = sorted({int(i) for i in indices if 0 <= int(i) < len(self.notes)})
        if not valid:
            return {"ok": False, "status": "No selected notes"}
        path = self._dialog(webview.FileDialog.SAVE, file_types=MIDI_FILE_TYPES, save_filename="selected.mid")
        if not path:
            return {"ok": False, "status": "Cancelled"}
        if Path(path).suffix.lower() not in {".mid", ".midi"}:
            path += ".mid"
        with self._lock:
            shift = int(self.settings["exportOctave"]) * 12 + int(self.settings["exportSemitone"])
            notes = [self.notes[i].with_pitch_offset(shift) for i in valid]
            bpm = float(self.settings["bpm"])
        export_midi(notes, path, bpm=bpm)
        with self._lock:
            self._status = f"Exported {len(notes)} selected note(s): {Path(path).name}"
        return {"ok": True, "path": str(path), "status": self._status}

    # ------------------------------------------------------------------
    # Quick Hz tools
    # ------------------------------------------------------------------
    def calculate_quick_hz(self, options: dict[str, Any]) -> dict[str, Any]:
        bpm = float(options.get("bpm", self.settings.get("bpm", 175.0)))
        hz = float(options.get("hz", 16.0))
        start_floor = max(0, int(options.get("startFloor", 0)))
        use_end = bool(options.get("useEndFloor", False))
        if use_end:
            count = ResolveGenerateCount(start_floor, end_floor=int(options.get("endFloor", start_floor + 16)))
        else:
            count = ResolveGenerateCount(start_floor, count=int(options.get("count", 16)))
        add_set_speed = bool(options.get("addSetSpeed", True))
        info = CalculateHzInfo(bpm, hz)
        output = GenerateOutputText(info, start_floor, count, add_set_speed=add_set_speed)
        return {
            "info": {
                "intervalMs": info.interval_ms,
                "beatMs": info.beat_ms,
                "beatsPerHit": info.beats_per_hit,
                "beatFractionText": info.beat_fraction_text,
                "relativeAngle": info.relative_angle,
                "equivalentBpm": info.equivalent_bpm,
            },
            "startFloor": start_floor,
            "count": count,
            "output": output,
        }

    def choose_quick_hz_chart(self) -> dict[str, Any]:
        path = self._dialog(webview.FileDialog.OPEN, file_types=ADOF_FILE_TYPES)
        if not path:
            return {"ok": False, "status": "Cancelled"}
        tail = ReadChartTailFloor(path)
        return {"ok": True, "path": str(Path(path).resolve()), "tailFloor": tail, "status": f"Chart tail: floor {tail}"}

    def append_quick_hz_chart(self, chart_path: str, options: dict[str, Any]) -> dict[str, Any]:
        if not chart_path:
            return {"ok": False, "status": "No ADOFAI chart selected"}
        calculated = self.calculate_quick_hz(options)
        info = CalculateHzInfo(float(options.get("bpm", 175.0)), float(options.get("hz", 16.0)))
        data, result = AppendGeneratedDataToChart(
            chart_path,
            info,
            int(calculated["count"]),
            start_floor=None,
            add_set_speed=bool(options.get("addSetSpeed", True)),
        )
        output_path = SaveChartAs(data, chart_path, overwrite=bool(options.get("overwrite", False)))
        return {
            "ok": True,
            "path": str(output_path),
            "tiles": result.angle_data_added,
            "actions": result.actions_added,
            "status": f"Appended {result.angle_data_added} tiles / {result.actions_added} actions: {output_path}",
        }

    def save_quick_hz_text(self, text: str) -> dict[str, Any]:
        if not str(text).strip():
            return {"ok": False, "status": "No output"}
        path = self._dialog(webview.FileDialog.SAVE, file_types=("Text File (*.txt)", "All files (*.*)"), save_filename="quick_hz_output.txt")
        if not path:
            return {"ok": False, "status": "Cancelled"}
        if Path(path).suffix.lower() != ".txt":
            path += ".txt"
        Path(path).write_text(str(text), encoding="utf-8")
        return {"ok": True, "path": path, "status": f"Saved {path}"}

    # ------------------------------------------------------------------
    # Harmonic diagram
    # ------------------------------------------------------------------
    @staticmethod
    def _parse_ratio_fraction(text: str) -> Fraction:
        s = str(text).strip()
        if not s:
            raise ValueError("empty ratio")
        if ":" in s:
            a, b = s.split(":", 1)
            value = Fraction(a.strip()) / Fraction(b.strip())
        else:
            value = Fraction(s)
        if value <= 0:
            raise ValueError("ratio must be positive")
        return value

    @staticmethod
    def _factor_int(value: int) -> dict[int, int]:
        n = abs(int(value)); factors: dict[int, int] = {}; d = 2
        while d * d <= n:
            while n % d == 0:
                factors[d] = factors.get(d, 0) + 1; n //= d
            d += 1 if d == 2 else 2
        if n > 1:
            factors[n] = factors.get(n, 0) + 1
        return factors

    @classmethod
    def _dimension_ratio_fraction(cls, ratio: Fraction) -> Fraction:
        r = Fraction(ratio)
        if r <= 0:
            raise ValueError("ratio must be positive")
        generators = {2: Fraction(2, 1), 3: Fraction(3, 2), 5: Fraction(5, 4), 7: Fraction(7, 4), 11: Fraction(11, 4)}
        exponents: dict[int, int] = {}
        for p, e in cls._factor_int(r.numerator).items(): exponents[p] = exponents.get(p, 0) + e
        for p, e in cls._factor_int(r.denominator).items(): exponents[p] = exponents.get(p, 0) - e
        out = Fraction(1, 1)
        for p, e in sorted(exponents.items()):
            gen = generators.get(p)
            if gen is None:
                raise ValueError(f"unsupported dimension prime: {p}")
            out = out * (gen ** e) if e >= 0 else out / (gen ** (-e))
        return out

    @staticmethod
    def _format_ratio(ratio: Fraction) -> str:
        value = float(ratio)
        return f"{ratio.numerator}/{ratio.denominator} ({value:.6f})" if ratio.denominator <= 100000 and abs(value) < 100000 else f"{value:.6f}"

    @staticmethod
    def _caftaphata_pitch_number(ratio: float, edo: int = 41, offset: int = 2) -> int:
        edo = max(1, int(edo))
        return (int(offset) + int(round(edo * math.log2(max(1e-12, float(ratio)))))) % edo

    def get_harmonic_diagram_defaults(self, selected_indices: list[int] | None = None) -> dict[str, Any]:
        root_hz = 261.625565
        valid = [int(i) for i in (selected_indices or []) if 0 <= int(i) < len(self.notes)]
        if valid:
            root_hz = 440.0 * (2.0 ** ((float(self.notes[valid[0]].midi) - 69.0) / 12.0))
        return {
            "rootHz": root_hz,
            "rootShift": "1",
            "base1dOffset": 0,
            "harmonics": "1/3,1,3,7,9",
            "timeUnit": "seconds",
            "bpm": float(self.settings.get("bpm", 175.0)),
            "start": float(self.player.time),
            "duration": 1.0,
            "edo": 41,
            "offset": 2,
        }

    def _harmonic_diagram_rows(self, options: dict[str, Any]) -> tuple[list[dict[str, Any]], float, float]:
        root_hz = max(0.001, float(options.get("rootHz", 261.625565)))
        shift = self._parse_ratio_fraction(str(options.get("rootShift", "1")))
        vals = [self._parse_ratio_fraction(x) for x in str(options.get("harmonics", "1/3,1,3,7,9")).replace(";", ",").split(",") if x.strip()]
        if not vals:
            raise ValueError("harmonics list is empty")
        one_d = int(options.get("base1dOffset", 0))
        offset_factor = Fraction(2, 1) ** one_d if one_d >= 0 else Fraction(1, 2) ** (-one_d)
        base_rep = self._dimension_ratio_fraction(shift) * offset_factor
        start = max(0.0, float(options.get("start", self.player.time)))
        duration = max(0.001, float(options.get("duration", 1.0)))
        if str(options.get("timeUnit", "seconds")) == "beats":
            beat_sec = 60.0 / max(1e-9, float(options.get("bpm", self.settings.get("bpm", 175.0))))
            start *= beat_sec; duration *= beat_sec
        edo = max(1, min(999, int(options.get("edo", 41)))); offset = max(-999, min(999, int(options.get("offset", 2))))
        rows: list[dict[str, Any]] = []
        for local in vals:
            raw_ratio = shift * local
            local_rep = self._dimension_ratio_fraction(local)
            ratio = base_rep * local_rep
            hz = root_hz * float(ratio)
            midi = 69.0 + 12.0 * math.log2(max(1e-12, hz) / 440.0)
            rows.append({
                "local": self._format_ratio(local),
                "dimension": self._format_ratio(local_rep),
                "ratio": self._format_ratio(ratio),
                "hz": hz,
                "midi": midi,
                "pitchNumber": self._caftaphata_pitch_number(float(raw_ratio), edo=edo, offset=offset),
            })
        return rows, start, duration

    def preview_harmonic_diagram(self, options: dict[str, Any]) -> dict[str, Any]:
        rows, start, duration = self._harmonic_diagram_rows(options)
        return {"rows": rows, "startSeconds": start, "endSeconds": start + duration, "durationSeconds": duration}

    def insert_harmonic_diagram(self, options: dict[str, Any]) -> dict[str, Any]:
        rows, start, duration = self._harmonic_diagram_rows(options)
        with self._lock:
            self._push_undo()
            first = len(self.notes)
            for row in rows:
                self.notes.append(Note(start, start + duration, float(row["midi"])).normalized())
            indices = list(range(first, len(self.notes)))
            self.duration = max(self.duration, start + duration)
            self._sync_notes_to_player()
            self._dirty = True
            numbers = ", ".join(str(row["pitchNumber"]) for row in rows)
            self._status = f"Inserted {len(rows)} harmonic note(s): {numbers}"
            return {"notes": self._note_dicts(), "status": self._status, "indices": indices}

    # ------------------------------------------------------------------
    # Language / update
    # ------------------------------------------------------------------
    def get_language_state(self) -> dict[str, Any]:
        return {"current": current_language(), "available": available_languages()}

    def set_app_language(self, language: str) -> dict[str, Any]:
        set_language(language)
        return {"current": current_language(), "restartRequired": True, "status": tr("dialog.language.restart")}

    def get_update_info(self) -> dict[str, Any]:
        return {"version": "0.7.2", "text": tr("update.open_releases_text", version="0.7.2"), "info": tr("update.open_releases_info")}
