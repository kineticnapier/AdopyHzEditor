from __future__ import annotations

from typing import Any

from core.note_model import Note, hz_to_midi, midi_to_hz


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(value)))


def _lerp(a: float, b: float, t: float) -> float:
    return float(a) + (float(b) - float(a)) * float(t)


def _split_cubic(values: tuple[float, float, float, float], t: float) -> tuple[tuple[float, float, float, float], tuple[float, float, float, float]]:
    p0, p1, p2, p3 = values
    q0 = _lerp(p0, p1, t)
    q1 = _lerp(p1, p2, t)
    q2 = _lerp(p2, p3, t)
    r0 = _lerp(q0, q1, t)
    r1 = _lerp(q1, q2, t)
    s = _lerp(r0, r1, t)
    return (p0, q0, r0, s), (s, r1, q2, p3)


class EditingMixin:
    """DAW-style editing operations layered on top of NoteMixin."""

    def _split_note_exact(self, note: Note, at_time: float) -> tuple[Note, Note]:
        n = note.normalized()
        t = _clamp((float(at_time) - n.start) / max(1e-12, n.duration), 0.0, 1.0)
        if not n.is_curve:
            return (
                Note(n.start, at_time, n.midi, n.velocity, target_angle=n.target_angle).normalized(),
                Note(at_time, n.end, n.midi, n.velocity, target_angle=n.target_angle).normalized(),
            )

        mode = (n.interpolation or "bezier_pitch").lower().replace("-", "_").replace(" ", "_")
        p0 = float(n.midi)
        p3 = float(n.midi_end if n.midi_end is not None else p0)
        p1 = float(n.ctrl1_midi if n.ctrl1_midi is not None else p0)
        p2 = float(n.ctrl2_midi if n.ctrl2_midi is not None else p3)

        if mode == "bezier_hz":
            left_hz, right_hz = _split_cubic(tuple(midi_to_hz(x) for x in (p0, p1, p2, p3)), t)
            left_vals = tuple(hz_to_midi(max(1e-12, x)) for x in left_hz)
            right_vals = tuple(hz_to_midi(max(1e-12, x)) for x in right_hz)
        elif mode == "bezier_pitch":
            left_vals, right_vals = _split_cubic((p0, p1, p2, p3), t)
        else:
            mid = float(n.midi_at(t))
            left_vals = (p0, p0, mid, mid)
            right_vals = (mid, mid, p3, p3)

        left = Note(
            n.start,
            at_time,
            left_vals[0],
            n.velocity,
            "curve",
            left_vals[3],
            left_vals[1],
            left_vals[2],
            n.interpolation,
            n.target_angle,
        ).normalized()
        right = Note(
            at_time,
            n.end,
            right_vals[0],
            n.velocity,
            "curve",
            right_vals[3],
            right_vals[1],
            right_vals[2],
            n.interpolation,
            n.target_angle,
        ).normalized()
        return left, right

    def split_notes(self, indices: list[int], at_time: float) -> dict[str, Any]:
        with self._lock:
            valid = set(self._valid_indices(indices))
            if not valid:
                return {"notes": self._note_dicts(), "indices": [], "status": "ノートが選択されていません"}
            t = self._snap_time(float(at_time))
            split_count = 0
            new_notes: list[Note] = []
            new_indices: list[int] = []
            for i, raw_note in enumerate(self.notes):
                n = raw_note.normalized()
                if i in valid and n.start + 0.001 < t < n.end - 0.001:
                    if split_count == 0:
                        self._push_undo()
                    left, right = self._split_note_exact(n, t)
                    new_indices.extend([len(new_notes), len(new_notes) + 1])
                    new_notes.extend([left, right])
                    split_count += 1
                else:
                    new_notes.append(n)
            if split_count == 0:
                return {"notes": self._note_dicts(), "indices": [], "status": "再生位置をまたぐ選択ノートがありません"}
            self.notes = new_notes
            self._dirty = True
            self._sync_notes_to_player()
            self._status = f"{split_count}個のノートを分割しました"
            return {"notes": self._note_dicts(), "indices": new_indices, "status": self._status}

    def duplicate_notes_shifted(self, indices: list[int], dx: float, dy: float) -> dict[str, Any]:
        with self._lock:
            valid = self._valid_indices(indices)
            if not valid:
                return {"notes": self._note_dicts(), "indices": [], "status": "ノートが選択されていません"}
            source = [self.notes[i].normalized() for i in valid]
            min_start = min(n.start for n in source)
            max_end = max(n.end for n in source)
            dx = _clamp(float(dx), -min_start, max(0.0, self.duration - max_end))
            if self.settings["snapEnabled"]:
                dx = self._snap_time(source[0].start + dx) - source[0].start
                dx = _clamp(dx, -min_start, max(0.0, self.duration - max_end))

            pitches: list[float] = []
            for n in source:
                pitches.extend(x for x in (n.midi, n.midi_end, n.ctrl1_midi, n.ctrl2_midi) if x is not None)
            if pitches:
                dy = _clamp(float(dy), self.midi_min - min(pitches), self.midi_max - max(pitches))

            self._push_undo()
            new_indices: list[int] = []
            for n in source:
                self.notes.append(n.shifted(dx=dx, dy=dy).normalized())
                new_indices.append(len(self.notes) - 1)
            self._dirty = True
            self._sync_notes_to_player()
            self._status = f"{len(new_indices)}個のノートをドラッグ複製しました"
            return {"notes": self._note_dicts(), "indices": new_indices, "status": self._status}

    def bulk_edit_notes(self, indices: list[int], changes: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            valid = self._valid_indices(indices)
            if not valid:
                return {"notes": self._note_dicts(), "status": "ノートが選択されていません"}
            if not isinstance(changes, dict):
                raise TypeError("changes must be an object")

            notes = [self.notes[i].normalized() for i in valid]
            time_delta = float(changes.get("timeDelta", 0.0))
            pitch_delta = float(changes.get("pitchDelta", 0.0))
            duration_value = changes.get("duration")
            align = str(changes.get("align", ""))

            min_start = min(n.start for n in notes)
            max_end = max(n.end for n in notes)
            time_delta = _clamp(time_delta, -min_start, max(0.0, self.duration - max_end))
            if self.settings["snapEnabled"] and abs(time_delta) > 1e-12:
                time_delta = self._snap_time(notes[0].start + time_delta) - notes[0].start

            pitches: list[float] = []
            for n in notes:
                pitches.extend(x for x in (n.midi, n.midi_end, n.ctrl1_midi, n.ctrl2_midi) if x is not None)
            if pitches:
                pitch_delta = _clamp(pitch_delta, self.midi_min - min(pitches), self.midi_max - max(pitches))

            align_start = min(n.start for n in notes)
            align_end = max(n.end for n in notes)
            self._push_undo()
            for i, n in zip(valid, notes):
                edited = n.shifted(dx=time_delta, dy=pitch_delta).normalized()
                if duration_value is not None:
                    duration = max(0.001, float(duration_value))
                    end = min(self.duration, edited.start + duration)
                    if end <= edited.start:
                        end = min(self.duration, edited.start + 0.001)
                    edited = self._with_times(edited, edited.start, end)
                if align == "start":
                    start = min(align_start, edited.end - 0.001)
                    edited = self._with_times(edited, start, edited.end)
                elif align == "end":
                    end = max(align_end, edited.start + 0.001)
                    end = min(self.duration, end)
                    edited = self._with_times(edited, edited.start, end)
                self.notes[i] = edited

            self._dirty = True
            self._sync_notes_to_player()
            self._status = f"{len(valid)}個のノートを一括編集しました"
            return {"notes": self._note_dicts(), "status": self._status}
