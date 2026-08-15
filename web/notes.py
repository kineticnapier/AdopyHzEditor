from __future__ import annotations

from typing import Any, Iterable

from core.note_model import Note


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

    def _with_times(self, note: Note, start: float, end: float) -> Note:
        n = note.normalized()
        return Note(
            float(start),
            float(end),
            n.midi,
            n.velocity,
            n.kind,
            n.midi_end,
            n.ctrl1_midi,
            n.ctrl2_midi,
            n.interpolation,
            n.target_angle,
        ).normalized()

    def _valid_indices(self, indices: list[int]) -> list[int]:
        return sorted({int(i) for i in indices if 0 <= int(i) < len(self.notes)})

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
            self._status = "カーブを追加しました" if note.is_curve else "ノートを追加しました"
            return {"index": len(self.notes) - 1, "notes": self._note_dicts(), "status": self._status}

    def delete_notes(self, indices: list[int]) -> dict[str, Any]:
        with self._lock:
            valid = sorted(self._valid_indices(indices), reverse=True)
            if not valid:
                return {"notes": self._note_dicts(), "status": "ノートが選択されていません"}
            self._push_undo()
            for i in valid:
                self.notes.pop(i)
            self._dirty = True
            self._sync_notes_to_player()
            self._status = f"{len(valid)}個のノートを削除しました"
            return {"notes": self._note_dicts(), "status": self._status}

    def move_notes(self, indices: list[int], dx: float, dy: float) -> dict[str, Any]:
        with self._lock:
            valid = self._valid_indices(indices)
            if not valid:
                return {"notes": self._note_dicts(), "status": "ノートが選択されていません"}
            original = [self.notes[i].normalized() for i in valid]
            min_start = min(n.start for n in original)
            max_end = max(n.end for n in original)
            dx = _clamp(dx, -min_start, max(0.0, self.duration - max_end))

            pitch_values: list[float] = []
            for n in original:
                pitch_values.extend(v for v in (n.midi, n.midi_end, n.ctrl1_midi, n.ctrl2_midi) if v is not None)
            if pitch_values:
                dy = _clamp(dy, self.midi_min - min(pitch_values), self.midi_max - max(pitch_values))

            # Snap the group using its first note so relative spacing is preserved.
            if self.settings["snapEnabled"] and original:
                snapped_first = self._snap_time(original[0].start + dx)
                dx = snapped_first - original[0].start
                dx = _clamp(dx, -min_start, max(0.0, self.duration - max_end))

            self._push_undo()
            for i, n in zip(valid, original):
                self.notes[i] = n.shifted(dx=float(dx), dy=float(dy)).normalized()
            self._dirty = True
            self._sync_notes_to_player()
            self._status = f"{len(valid)}個のノートを移動しました"
            return {"notes": self._note_dicts(), "status": self._status}

    def resize_notes(self, indices: list[int], edge: str, delta_seconds: float) -> dict[str, Any]:
        """Resize selected notes from the left or right edge.

        Every selected note moves the same edge by the same delta. Time snap is
        applied to each changed edge, while pitch/curve control points are kept.
        """
        with self._lock:
            valid = self._valid_indices(indices)
            if not valid:
                return {"notes": self._note_dicts(), "status": "ノートが選択されていません"}
            edge_key = str(edge).lower()
            if edge_key not in {"start", "end"}:
                raise ValueError("edge must be start or end")
            minimum = 0.001
            original = [self.notes[i].normalized() for i in valid]
            self._push_undo()
            for i, n in zip(valid, original):
                if edge_key == "start":
                    new_start = self._snap_time(n.start + float(delta_seconds))
                    new_start = min(new_start, n.end - minimum)
                    new_start = max(0.0, new_start)
                    self.notes[i] = self._with_times(n, new_start, n.end)
                else:
                    new_end = self._snap_time(n.end + float(delta_seconds))
                    new_end = max(new_end, n.start + minimum)
                    new_end = min(float(self.duration), new_end)
                    self.notes[i] = self._with_times(n, n.start, new_end)
            self._dirty = True
            self._sync_notes_to_player()
            side = "左端" if edge_key == "start" else "右端"
            self._status = f"{len(valid)}個のノートの{side}を変更しました"
            return {"notes": self._note_dicts(), "status": self._status}

    def set_note_properties(self, index: int, changes: dict[str, Any]) -> dict[str, Any]:
        """Set exact properties for one selected note from the inspector."""
        with self._lock:
            i = int(index)
            if i < 0 or i >= len(self.notes):
                return {"notes": self._note_dicts(), "status": "ノートが選択されていません"}
            if not isinstance(changes, dict):
                raise TypeError("changes must be an object")
            n = self.notes[i].normalized()
            start = float(changes.get("start", n.start))
            end = float(changes.get("end", n.end))
            if "duration" in changes:
                end = start + max(0.001, float(changes["duration"]))
            start = _clamp(start, 0.0, self.duration)
            end = _clamp(end, 0.0, self.duration)
            if end < start + 0.001:
                end = min(self.duration, start + 0.001)
                if end <= start:
                    start = max(0.0, end - 0.001)
            updated = self._with_times(n, start, end)
            if "midi" in changes:
                target = self._snap_pitch(float(changes["midi"]))
                updated = updated.with_pitch_offset(target - updated.midi)
            if "velocity" in changes:
                v = max(0, min(127, int(round(float(changes["velocity"])))))
                u = updated.normalized()
                updated = Note(u.start, u.end, u.midi, v, u.kind, u.midi_end, u.ctrl1_midi, u.ctrl2_midi, u.interpolation, u.target_angle).normalized()
            self._push_undo()
            self.notes[i] = updated
            self._dirty = True
            self._sync_notes_to_player()
            self._status = "ノートのプロパティを更新しました"
            return {"notes": self._note_dicts(), "index": i, "status": self._status}

    def duplicate_notes(self, indices: list[int]) -> dict[str, Any]:
        with self._lock:
            valid = self._valid_indices(indices)
            if not valid:
                return {"notes": self._note_dicts(), "indices": [], "status": "ノートが選択されていません"}
            source = [self.notes[i].normalized() for i in valid]
            first = min(n.start for n in source)
            last = max(n.end for n in source)
            offset = max(0.001, last - first)
            if last + offset > self.duration:
                offset = max(0.0, self.duration - last)
            if offset <= 1e-9:
                return {"notes": self._note_dicts(), "indices": [], "status": "右側に複製する空きがありません"}
            self._push_undo()
            new_indices: list[int] = []
            for n in source:
                self.notes.append(n.with_time_offset(offset).normalized())
                new_indices.append(len(self.notes) - 1)
            self._dirty = True
            self._sync_notes_to_player()
            self._status = f"{len(new_indices)}個のノートを複製しました"
            return {"notes": self._note_dicts(), "indices": new_indices, "status": self._status}

    def quantize_notes(self, indices: list[int]) -> dict[str, Any]:
        with self._lock:
            valid = self._valid_indices(indices)
            if not valid:
                return {"notes": self._note_dicts(), "status": "ノートが選択されていません"}
            step = 60.0 / max(1e-6, float(self.settings["bpm"])) / max(1, int(self.settings["snapDiv"]))
            offset = float(self.settings["offsetMs"]) / 1000.0

            def q(t: float) -> float:
                return _clamp(offset + round((float(t) - offset) / step) * step, 0.0, self.duration)

            self._push_undo()
            for i in valid:
                n = self.notes[i].normalized()
                a = q(n.start)
                b = q(n.end)
                if b <= a:
                    b = min(self.duration, a + step)
                if b <= a:
                    a = max(0.0, b - max(0.001, step))
                self.notes[i] = self._with_times(n, a, b)
            self._dirty = True
            self._sync_notes_to_player()
            self._status = f"{len(valid)}個のノートをクオンタイズしました"
            return {"notes": self._note_dicts(), "status": self._status}

    def apply_interpolation(self, indices: list[int]) -> dict[str, Any]:
        with self._lock:
            valid = sorted({int(i) for i in indices if 0 <= int(i) < len(self.notes) and self.notes[int(i)].is_curve})
            if not valid:
                return {"notes": self._note_dicts(), "status": "カーブノートが選択されていません"}
            self._push_undo()
            mode = str(self.settings["curveInterpolation"])
            for i in valid:
                self.notes[i] = self.notes[i].with_interpolation(mode)
            self._dirty = True
            self._sync_notes_to_player()
            self._status = f"{len(valid)}個のカーブに補間を適用しました"
            return {"notes": self._note_dicts(), "status": self._status}

    def apply_target_angle(self, indices: list[int]) -> dict[str, Any]:
        with self._lock:
            valid = self._valid_indices(indices)
            if not valid:
                return {"notes": self._note_dicts(), "status": "ノートが選択されていません"}
            self._push_undo()
            angle = float(self.settings["targetAngle"])
            for i in valid:
                self.notes[i] = self.notes[i].with_target_angle(angle)
            self._dirty = True
            self._status = f"{len(valid)}個のノートに{angle:.6f}°を適用しました"
            return {"notes": self._note_dicts(), "status": self._status}

    def clear_target_angle(self, indices: list[int]) -> dict[str, Any]:
        with self._lock:
            valid = self._valid_indices(indices)
            if not valid:
                return {"notes": self._note_dicts(), "status": "ノートが選択されていません"}
            self._push_undo()
            for i in valid:
                self.notes[i] = self.notes[i].with_target_angle(None)
            self._dirty = True
            self._status = f"{len(valid)}個のノートから角度指定を解除しました"
            return {"notes": self._note_dicts(), "status": self._status}

    def undo(self) -> dict[str, Any]:
        with self._lock:
            if not self._undo_stack:
                return {"notes": self._note_dicts(), "status": "元に戻せる操作がありません"}
            self._redo_stack.append(self._snapshot())
            self._restore_snapshot(self._undo_stack.pop())
            self._status = "元に戻しました"
            return {"notes": self._note_dicts(), "status": self._status}

    def redo(self) -> dict[str, Any]:
        with self._lock:
            if not self._redo_stack:
                return {"notes": self._note_dicts(), "status": "やり直せる操作がありません"}
            self._undo_stack.append(self._snapshot())
            self._restore_snapshot(self._redo_stack.pop())
            self._status = "やり直しました"
            return {"notes": self._note_dicts(), "status": self._status}

    def copy_notes(self, indices: list[int]) -> dict[str, Any]:
        with self._lock:
            valid = self._valid_indices(indices)
            if not valid:
                return {"status": "ノートが選択されていません"}
            selected = [self.notes[i].normalized() for i in valid]
            first = min(n.start for n in selected)
            self._clipboard = [n.with_time_offset(-first) for n in selected]
            self._status = f"{len(selected)}個のノートをコピーしました"
            return {"status": self._status}

    def cut_notes(self, indices: list[int]) -> dict[str, Any]:
        self.copy_notes(indices)
        return self.delete_notes(indices)

    def paste_notes(self, at_time: float) -> dict[str, Any]:
        with self._lock:
            if not self._clipboard:
                return {"notes": self._note_dicts(), "indices": [], "status": "クリップボードは空です"}
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
            self._status = f"{len(new_indices)}個のノートを貼り付けました"
            return {"notes": self._note_dicts(), "indices": new_indices, "status": self._status}
