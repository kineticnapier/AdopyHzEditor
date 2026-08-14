from __future__ import annotations

from typing import Any, Iterable

from note_model import Note


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(value)))


class NoteMixin:
    # ------------------------------------------------------------------
    # Notes / history / clipboard
    # ------------------------------------------------------------------
    def _snapshot(self) -> list[dict[str, Any]]:
        return self._note_dicts()

    def _push_undo(self) -> None:
        self._undo_stack.append(self._snapshot())
        if len(self._undo_stack) > 200:
            self._undo_stack.pop(0)
        self._redo_stack.clear()

    def _restore_snapshot(self, state: Iterable[dict[str, Any]]) -> None:
        self.notes = [Note.from_dict(dict(item)) for item in state]
        self._sync_notes_to_player()
        self._dirty = True

    def _sync_notes_to_player(self) -> None:
        self.player.set_preview_notes(self.notes)
        note_end = max((float(n.end) for n in self.notes), default=0.0)
        self.player.set_virtual_duration(max(float(self.duration), note_end, 0.001))
        self._apply_player_settings()

    def _snap_time(self, seconds: float) -> float:
        t = _clamp(seconds, 0.0, self.duration)
        if not self.settings["snapEnabled"]:
            return t
        step = 60.0 / max(1e-6, float(self.settings["bpm"])) / max(1, int(self.settings["snapDiv"]))
        offset = float(self.settings["offsetMs"]) / 1000.0
        return _clamp(offset + round((t - offset) / step) * step, 0.0, self.duration)

    def _snap_pitch(self, midi: float) -> float:
        step = max(1e-6, float(self.pitch_step))
        snapped = round(float(midi) / step) * step
        return _clamp(snapped, float(self.midi_min), float(self.midi_max))

    def _curve_controls(self, p0: float, p3: float) -> tuple[float, float]:
        d = float(p3) - float(p0)
        shape = str(self.settings["curveShape"])
        if shape == "linear":
            return p0 + d / 3.0, p0 + d * 2.0 / 3.0
        if shape == "ease_in":
            return p0, p0
        if shape == "ease_out":
            return p3, p3
        if shape == "s_curve":
            return p0 - d * 0.15, p3 + d * 0.15
        return p0, p3

    def add_note(self, start: float, end: float, midi: float, kind: str = "note", end_midi: float | None = None) -> dict[str, Any]:
        with self._lock:
            a, b = sorted((self._snap_time(start), self._snap_time(end)))
            if b - a < 0.001:
                step = 60.0 / max(1e-6, float(self.settings["bpm"])) / max(1, int(self.settings["snapDiv"])) if self.settings["snapEnabled"] else 0.02
                b = min(self.duration, a + max(0.02, step))
            p0 = self._snap_pitch(midi)
            self._push_undo()
            if str(kind) == "curve":
                p3 = self._snap_pitch(p0 if end_midi is None else end_midi)
                c1, c2 = self._curve_controls(p0, p3)
                note = Note(
                    a,
                    b,
                    p0,
                    100,
                    "curve",
                    p3,
                    c1,
                    c2,
                    str(self.settings["curveInterpolation"]),
                ).normalized()
            else:
                note = Note(a, b, p0).normalized()
            self.notes.append(note)
            self._dirty = True
            self._sync_notes_to_player()
            self._status = "Curve added" if note.is_curve else "Note added"
            return {"index": len(self.notes) - 1, "notes": self._note_dicts(), "status": self._status}

    def delete_notes(self, indices: list[int]) -> dict[str, Any]:
        with self._lock:
            valid = sorted({int(i) for i in indices if 0 <= int(i) < len(self.notes)}, reverse=True)
            if not valid:
                return {"notes": self._note_dicts(), "status": "No notes selected"}
            self._push_undo()
            for i in valid:
                self.notes.pop(i)
            self._dirty = True
            self._sync_notes_to_player()
            self._status = f"Deleted {len(valid)} note(s)"
            return {"notes": self._note_dicts(), "status": self._status}

    def move_notes(self, indices: list[int], dx: float, dy: float) -> dict[str, Any]:
        with self._lock:
            valid = sorted({int(i) for i in indices if 0 <= int(i) < len(self.notes)})
            if not valid:
                return {"notes": self._note_dicts(), "status": "No notes selected"}
            original = [self.notes[i].normalized() for i in valid]
            min_start = min(n.start for n in original)
            max_end = max(n.end for n in original)
            dx = _clamp(dx, -min_start, max(0.0, self.duration - max_end))

            pitch_values: list[float] = []
            for n in original:
                pitch_values.extend(
                    v for v in (n.midi, n.midi_end, n.ctrl1_midi, n.ctrl2_midi) if v is not None
                )
            if pitch_values:
                dy = _clamp(dy, self.midi_min - min(pitch_values), self.midi_max - max(pitch_values))

            self._push_undo()
            for i, n in zip(valid, original):
                self.notes[i] = n.shifted(dx=float(dx), dy=float(dy)).normalized()
            self._dirty = True
            self._sync_notes_to_player()
            self._status = f"Moved {len(valid)} note(s)"
            return {"notes": self._note_dicts(), "status": self._status}

    def apply_interpolation(self, indices: list[int]) -> dict[str, Any]:
        with self._lock:
            valid = sorted({int(i) for i in indices if 0 <= int(i) < len(self.notes) and self.notes[int(i)].is_curve})
            if not valid:
                return {"notes": self._note_dicts(), "status": "No curve notes selected"}
            self._push_undo()
            mode = str(self.settings["curveInterpolation"])
            for i in valid:
                self.notes[i] = self.notes[i].with_interpolation(mode)
            self._dirty = True
            self._sync_notes_to_player()
            self._status = f"Applied {mode} to {len(valid)} curve(s)"
            return {"notes": self._note_dicts(), "status": self._status}

    def apply_target_angle(self, indices: list[int]) -> dict[str, Any]:
        with self._lock:
            valid = sorted({int(i) for i in indices if 0 <= int(i) < len(self.notes)})
            if not valid:
                return {"notes": self._note_dicts(), "status": "No notes selected"}
            self._push_undo()
            angle = float(self.settings["targetAngle"])
            for i in valid:
                self.notes[i] = self.notes[i].with_target_angle(angle)
            self._dirty = True
            self._status = f"Applied {angle:.6f}° to {len(valid)} note(s)"
            return {"notes": self._note_dicts(), "status": self._status}

    def clear_target_angle(self, indices: list[int]) -> dict[str, Any]:
        with self._lock:
            valid = sorted({int(i) for i in indices if 0 <= int(i) < len(self.notes)})
            if not valid:
                return {"notes": self._note_dicts(), "status": "No notes selected"}
            self._push_undo()
            for i in valid:
                self.notes[i] = self.notes[i].with_target_angle(None)
            self._dirty = True
            self._status = f"Cleared angle from {len(valid)} note(s)"
            return {"notes": self._note_dicts(), "status": self._status}

    def undo(self) -> dict[str, Any]:
        with self._lock:
            if not self._undo_stack:
                return {"notes": self._note_dicts(), "status": "Nothing to undo"}
            self._redo_stack.append(self._snapshot())
            self._restore_snapshot(self._undo_stack.pop())
            self._status = "Undo"
            return {"notes": self._note_dicts(), "status": self._status}

    def redo(self) -> dict[str, Any]:
        with self._lock:
            if not self._redo_stack:
                return {"notes": self._note_dicts(), "status": "Nothing to redo"}
            self._undo_stack.append(self._snapshot())
            self._restore_snapshot(self._redo_stack.pop())
            self._status = "Redo"
            return {"notes": self._note_dicts(), "status": self._status}

    def copy_notes(self, indices: list[int]) -> dict[str, Any]:
        with self._lock:
            valid = sorted({int(i) for i in indices if 0 <= int(i) < len(self.notes)})
            if not valid:
                return {"status": "No notes selected"}
            selected = [self.notes[i].normalized() for i in valid]
            first = min(n.start for n in selected)
            self._clipboard = [n.with_time_offset(-first) for n in selected]
            self._status = f"Copied {len(selected)} note(s)"
            return {"status": self._status}

    def cut_notes(self, indices: list[int]) -> dict[str, Any]:
        self.copy_notes(indices)
        return self.delete_notes(indices)

    def paste_notes(self, at_time: float) -> dict[str, Any]:
        with self._lock:
            if not self._clipboard:
                return {"notes": self._note_dicts(), "indices": [], "status": "Clipboard is empty"}
            self._push_undo()
            base = _clamp(at_time, 0.0, self.duration)
            new_indices: list[int] = []
            for item in self._clipboard:
                pasted = item.with_time_offset(base).normalized()
                if pasted.end > self.duration:
                    pasted = pasted.shifted(dx=max(0.0, self.duration - pasted.end))
                self.notes.append(pasted)
                new_indices.append(len(self.notes) - 1)
            self._dirty = True
            self._sync_notes_to_player()
            self._status = f"Pasted {len(new_indices)} note(s)"
            return {"notes": self._note_dicts(), "indices": new_indices, "status": self._status}
