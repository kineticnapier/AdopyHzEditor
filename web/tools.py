from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import webview

from app_metadata import APP_VERSION
from exporters.midi import export_midi
from i18n import available_languages, current_language, set_language, tr
from core.note_model import Note
from core.project_io import load_project
PROJECT_FILE_TYPES = (
    "AdopyHzEditor Project (*.adopyhz;*.ahe.json)",
    "JSON (*.json)",
    "All files (*.*)",
)
MIDI_FILE_TYPES = ("MIDI Files (*.mid;*.midi)", "All files (*.*)")


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
        # Existing notes are explicitly preserved by this operation, so the
        # editable document duration must not become shorter than their tail.
        duration = max(duration, max((float(n.end) for n in self.notes), default=0.0))
        midi_min = max(0, min(127, int(options.get("midiMin", self.midi_min))))
        midi_max = max(0, min(127, int(options.get("midiMax", self.midi_max))))
        if midi_max <= midi_min:
            midi_max = min(127, midi_min + 12)
            if midi_max <= midi_min:
                midi_min = max(0, midi_max - 12)

        with self._lock:
            self.player.stop()
            self._detach_active_audio()
            # A blank workspace is a derived document. Keeping the previous
            # save target would let Ctrl+S overwrite the source project after
            # its audio reference has deliberately been removed.
            self.project_path = None
            self.project_audio_reference = None
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
            self._status = tr("msg.blank_workspace", seconds=f"{duration:.3f}", low=midi_min, high=midi_max)
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
            # Notes-only loading creates a derived workspace. Keeping the source
            # project path would let a normal save overwrite it without audio.
            self.project_path = None
            self._detach_active_audio()
            self.project_audio_reference = None
            self._fit_blank_bounds_to_notes()
            self._sync_notes_to_player()
            self._dirty = True
            self._status = tr("msg.loaded_notes_only", name=Path(path).name)
            return self._state_dict()

    def merge_project_notes_dialog(self) -> dict[str, Any]:
        path = self._dialog(webview.FileDialog.OPEN, file_types=PROJECT_FILE_TYPES)
        if not path:
            return self.get_state()
        _audio, notes, _settings = load_project(path)
        if not notes:
            with self._lock:
                self._status = tr("msg.no_notes_in", name=Path(path).name)
                return self._state_dict()
        with self._lock:
            self._push_undo()
            self.notes = sorted(
                [n.normalized() for n in self.notes] + [n.normalized() for n in notes],
                key=lambda n: (n.start, n.midi, n.end),
            )
            self.duration = max(self.duration, max(n.end for n in self.notes))
            if self.audio_path is None:
                self._fit_blank_bounds_to_notes()
            self._sync_notes_to_player()
            self._dirty = True
            self._status = tr("msg.merged_notes", count=len(notes), name=Path(path).name)
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
        if self.notes:
            first = min(n.start for n in self.notes)
            last = max(n.end for n in self.notes)
            start = max(0.0, first - 0.25)
            window = max(0.2, min(self.duration - start, max(1.0, last - start + 0.5)))
        else:
            start = 0.0
            window = min(12.0, self.duration)
        self.view.update(start=start, windowSeconds=window, pitchBottom=self.midi_min, visibleNotes=visible)
        self.player.set_virtual_duration(self.duration)

    def export_selected_midi_dialog(self, indices: list[int]) -> dict[str, Any]:
        valid = sorted({int(i) for i in indices if 0 <= int(i) < len(self.notes)})
        if not valid:
            return {"ok": False, "status": tr("msg.no_selected_notes")}
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
            self._status = tr("msg.exported_selected", count=len(notes), name=Path(path).name)
        return {"ok": True, "path": str(path), "status": self._status}

    # ------------------------------------------------------------------
    # Language / update
    # ------------------------------------------------------------------
    def get_language_state(self) -> dict[str, Any]:
        return {"current": current_language(), "available": available_languages()}

    def set_app_language(self, language: str) -> dict[str, Any]:
        set_language(language)
        return {"current": current_language(), "restartRequired": True, "status": tr("dialog.language.restart")}

    def get_update_info(self) -> dict[str, Any]:
        return {
            "version": APP_VERSION,
            "text": tr("update.open_releases_text", version=APP_VERSION),
            "info": tr("update.open_releases_info"),
        }
