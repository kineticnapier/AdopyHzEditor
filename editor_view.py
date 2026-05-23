from __future__ import annotations

from typing import Optional
from PySide6 import QtCore, QtGui, QtWidgets
import pyqtgraph as pg

from audio_analysis import Spectrogram, enhance_spectrogram
from note_model import Note, note_name


class EditorPlot(pg.PlotWidget):
    note_created = QtCore.Signal(float, float, int)
    note_delete_requested = QtCore.Signal(float, int)
    note_select_requested = QtCore.Signal(float, int, int)
    note_move_preview = QtCore.Signal(float, int)
    note_move_finished = QtCore.Signal(float, int)
    wheel_navigate = QtCore.Signal(int, int)  # delta, modifiers int

    def __init__(self) -> None:
        super().__init__()
        self.setBackground("k")
        self.showGrid(x=True, y=True, alpha=0.12)
        self.setLabel("bottom", "Time", units="s")
        self.setLabel("left", "Pitch")
        self.setMenuEnabled(False)
        self.plotItem.vb.setMouseEnabled(x=False, y=False)

        self._drag_start: Optional[QtCore.QPointF] = None
        self._drag_now: Optional[QtCore.QPointF] = None
        self._rubber: Optional[QtWidgets.QGraphicsRectItem] = None
        self._move_mode = False

        # EditorView injects this callable.
        # Callable[[float, int, int], bool]
        self.move_drag_checker = None

    def view_pos(self, ev) -> QtCore.QPointF:
        try:
            p = ev.position().toPoint()
        except AttributeError:
            p = ev.pos()
        scene = self.mapToScene(p)
        return self.plotItem.vb.mapSceneToView(scene)

    def mousePressEvent(self, ev: QtGui.QMouseEvent) -> None:
        view = self.view_pos(ev)
        mods_value = int(ev.modifiers().value)

        if ev.button() == QtCore.Qt.MouseButton.LeftButton:
            x = float(view.x())
            y = int(round(float(view.y())))

            # If clicked on an existing note, drag means move selected notes.
            if self.move_drag_checker is not None and self.move_drag_checker(x, y, mods_value):
                self._move_mode = True
                self._drag_start = view
                self._drag_now = view
                ev.accept()
                return

            self._move_mode = False
            self._drag_start = view
            self._drag_now = view
            ev.accept()
            return

        if ev.button() == QtCore.Qt.MouseButton.RightButton:
            self.note_delete_requested.emit(float(view.x()), int(round(view.y())))
            ev.accept()
            return

        ev.accept()

    def mouseMoveEvent(self, ev: QtGui.QMouseEvent) -> None:
        if self._drag_start is not None:
            self._drag_now = self.view_pos(ev)

            if self._move_mode:
                dx = float(self._drag_now.x() - self._drag_start.x())
                dy = int(round(float(self._drag_now.y() - self._drag_start.y())))
                self.note_move_preview.emit(dx, dy)
            else:
                self._update_rubber()
        ev.accept()

    def mouseReleaseEvent(self, ev: QtGui.QMouseEvent) -> None:
        if ev.button() == QtCore.Qt.MouseButton.LeftButton and self._drag_start is not None:
            end = self.view_pos(ev)
            start = self._drag_start
            self._clear_rubber()

            if self._move_mode:
                dx = float(end.x() - start.x())
                dy = int(round(float(end.y() - start.y())))
                self.note_move_finished.emit(dx, dy)
                self._drag_start = None
                self._drag_now = None
                self._move_mode = False
                ev.accept()
                return

            x1, x2 = float(start.x()), float(end.x())
            y = int(round((float(start.y()) + float(end.y())) * 0.5))

            if abs(x2 - x1) < 0.035:
                self.note_select_requested.emit(x1, y, int(ev.modifiers().value))
            else:
                a, b = sorted((x1, x2))
                if b - a >= 0.02:
                    self.note_created.emit(max(0.0, a), max(0.0, b), y)

            self._drag_start = None
            self._drag_now = None
        ev.accept()

    def wheelEvent(self, ev: QtGui.QWheelEvent) -> None:
        # 座標変換を使わず、外側のスライダーを動かすだけにする安全版
        try:
            delta = int(ev.angleDelta().y())
            mods = int(ev.modifiers().value)
            self.wheel_navigate.emit(delta, mods)
        finally:
            ev.accept()

    def _update_rubber(self) -> None:
        if self._drag_start is None or self._drag_now is None:
            return
        x1, x2 = float(self._drag_start.x()), float(self._drag_now.x())
        y = round((float(self._drag_start.y()) + float(self._drag_now.y())) * 0.5)
        rect = QtCore.QRectF(min(x1, x2), y - 0.45, abs(x2 - x1), 0.9)

        if self._rubber is None:
            self._rubber = QtWidgets.QGraphicsRectItem()
            self._rubber.setZValue(30)
            self._rubber.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 230), 0.02))
            self._rubber.setBrush(QtGui.QBrush(QtGui.QColor(100, 190, 255, 110)))
            self.plotItem.addItem(self._rubber)
        self._rubber.setRect(rect)

    def _clear_rubber(self) -> None:
        if self._rubber is not None:
            self.plotItem.removeItem(self._rubber)
            self._rubber = None


class EditorView(QtWidgets.QWidget):
    status_changed = QtCore.Signal(str)
    playhead_moved = QtCore.Signal(float)
    notes_changed = QtCore.Signal()

    def __init__(self) -> None:
        super().__init__()

        self.plot = EditorPlot()
        self.image = pg.ImageItem()
        self.image.setZValue(-10)
        self.plot.plotItem.addItem(self.image)

        self.playhead = pg.InfiniteLine(pos=0.0, angle=90, movable=True)
        self.playhead.setZValue(50)
        self.playhead.setPen(pg.mkPen((255, 255, 255, 230), width=2))
        self.plot.plotItem.addItem(self.playhead)
        self.playhead.sigPositionChanged.connect(self._on_playhead_moved)

        self.spectrogram: Spectrogram | None = None
        self.notes: list[Note] = []
        self.selected_index: int | None = None
        self.selected_indices: set[int] = set()
        self._note_items: list[QtWidgets.QGraphicsRectItem] = []
        self._guide_items: list[pg.InfiniteLine] = []
        self._suppress_playhead = False

        self.grid_enabled = False
        self.grid_bpm = 120.0
        self.grid_offset_sec = 0.0

        self.mode = 0
        self.contrast = 0.72
        self.gamma = 0.75
        self.enhance = True
        self.cmap = "viridis"
        self.harmonic_mode = "off"

        self.snap_enabled = False
        self.snap_bpm = 175.0
        self.snap_offset_sec = 0.0
        self.snap_division = 1

        self.undo_stack: list[list[dict]] = []
        self.redo_stack: list[list[dict]] = []
        self._move_original_state: list[dict] | None = None
        self._move_original_notes: list[tuple[int, Note]] = []
        self._move_active = False
        self._last_move_dx = 0.0
        self._last_move_dy = 0

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.plot)

        self.plot.move_drag_checker = self.start_move_drag
        self.plot.note_created.connect(self.add_note)
        self.plot.note_delete_requested.connect(self.delete_nearest)
        self.plot.note_select_requested.connect(self.select_nearest)
        self.plot.note_move_preview.connect(self.preview_move_selected)
        self.plot.note_move_finished.connect(self.finish_move_selected)

    def snapshot_state(self) -> list[dict]:
        return [n.normalized().to_dict() for n in self.notes]

    def restore_state(self, state: list[dict]) -> None:
        self.notes = [Note.from_dict(x) for x in state]
        self.selected_index = None
        self.selected_indices.clear()
        self.redraw_notes()
        self.notes_changed.emit()

    def clear_undo(self) -> None:
        self.undo_stack.clear()
        self.redo_stack.clear()

    def push_undo(self) -> None:
        self.undo_stack.append(self.snapshot_state())
        if len(self.undo_stack) > 200:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    def push_undo_state(self, state: list[dict]) -> None:
        self.undo_stack.append([dict(x) for x in state])
        if len(self.undo_stack) > 200:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    def undo(self) -> None:
        if not self.undo_stack:
            self.status_changed.emit("Nothing to undo")
            return
        current = self.snapshot_state()
        prev = self.undo_stack.pop()
        self.redo_stack.append(current)
        self.restore_state(prev)
        self.status_changed.emit("Undo")

    def redo(self) -> None:
        if not self.redo_stack:
            self.status_changed.emit("Nothing to redo")
            return
        current = self.snapshot_state()
        nxt = self.redo_stack.pop()
        self.undo_stack.append(current)
        self.restore_state(nxt)
        self.status_changed.emit("Redo")

    def start_move_drag(self, x: float, midi: int, mods_value: int) -> bool:
        # Ctrl/Shift click is reserved for multi-selection.
        ctrl = bool(mods_value & int(QtCore.Qt.KeyboardModifier.ControlModifier.value))
        shift = bool(mods_value & int(QtCore.Qt.KeyboardModifier.ShiftModifier.value))
        if ctrl or shift:
            return False

        idx = self.nearest_note_index(x, midi)
        if idx is None:
            return False

        if idx not in self.selected_indices:
            self.selected_indices = {idx}
            self.selected_index = idx
            self.redraw_notes()

        indices = sorted(i for i in self.selected_indices if 0 <= i < len(self.notes))
        if not indices:
            return False

        self._move_original_state = self.snapshot_state()
        self._move_original_notes = [(i, self.notes[i].normalized()) for i in indices]
        self._move_active = True
        self._last_move_dx = 0.0
        self._last_move_dy = 0
        return True

    def _clamp_move_delta(self, dx: float, dy: int) -> tuple[float, int]:
        if not self._move_original_notes:
            return dx, dy

        min_start = min(n.start for _, n in self._move_original_notes)
        max_end = max(n.end for _, n in self._move_original_notes)

        if self.spectrogram is not None:
            duration = self.spectrogram.duration
            dx = max(-min_start, min(dx, duration - max_end))
        else:
            dx = max(-min_start, dx)

        if self.snap_enabled:
            snapped = self.snap_time(min_start + dx)
            dx = snapped - min_start
            if self.spectrogram is not None:
                dx = max(-min_start, min(dx, self.spectrogram.duration - max_end))
            else:
                dx = max(-min_start, dx)

        min_midi = min(n.midi for _, n in self._move_original_notes)
        max_midi = max(n.midi for _, n in self._move_original_notes)
        low = 0
        high = 127
        if self.spectrogram is not None:
            low = max(0, self.spectrogram.midi_min)
            high = min(127, self.spectrogram.midi_max)

        dy = max(low - min_midi, min(dy, high - max_midi))
        return dx, int(dy)

    def preview_move_selected(self, dx: float, dy: int) -> None:
        if not self._move_active or not self._move_original_notes:
            return

        dx, dy = self._clamp_move_delta(float(dx), int(dy))
        self._last_move_dx = dx
        self._last_move_dy = dy

        for i, n in self._move_original_notes:
            self.notes[i] = Note(n.start + dx, n.end + dx, n.midi + dy, n.velocity).normalized()

        self.redraw_notes()

    def finish_move_selected(self, dx: float, dy: int) -> None:
        if not self._move_active:
            return

        self.preview_move_selected(dx, dy)

        moved = abs(self._last_move_dx) > 1e-7 or self._last_move_dy != 0
        if moved and self._move_original_state is not None:
            self.push_undo_state(self._move_original_state)
            self.notes_changed.emit()
            self.status_changed.emit(f"Moved {len(self._move_original_notes)} note(s): {self._last_move_dx:+.3f}s, {self._last_move_dy:+d} semitone(s)")
        else:
            if self._move_original_state is not None:
                self.restore_state(self._move_original_state)

        self._move_original_state = None
        self._move_original_notes = []
        self._move_active = False

    def nudge_selected(self, dx: float = 0.0, dy: int = 0) -> None:
        indices = sorted(i for i in self.selected_indices if 0 <= i < len(self.notes))
        if not indices:
            return

        self._move_original_state = self.snapshot_state()
        self._move_original_notes = [(i, self.notes[i].normalized()) for i in indices]
        dx, dy = self._clamp_move_delta(dx, dy)

        if abs(dx) <= 1e-9 and dy == 0:
            self._move_original_state = None
            self._move_original_notes = []
            return

        self.push_undo_state(self._move_original_state)
        for i, n in self._move_original_notes:
            self.notes[i] = Note(n.start + dx, n.end + dx, n.midi + dy, n.velocity).normalized()

        self._move_original_state = None
        self._move_original_notes = []
        self.redraw_notes()
        self.notes_changed.emit()
        self.status_changed.emit(f"Nudged {len(indices)} note(s): {dx:+.3f}s, {dy:+d} semitone(s)")

    def default_nudge_seconds(self) -> float:
        if self.snap_enabled:
            return 60.0 / max(1e-6, self.snap_bpm) / max(1, self.snap_division)
        return 0.05

    def set_spectrogram(self, spec: Spectrogram) -> None:
        self.spectrogram = spec
        self.refresh_image()
        self.image.setRect(QtCore.QRectF(0, spec.midi_min - 0.5, spec.duration, spec.midi_max - spec.midi_min + 1))
        self.set_view(0.0, min(12.0, spec.duration), spec.midi_min, min(60, spec.midi_max - spec.midi_min + 1))
        self.redraw_beat_grid()
        self.status_changed.emit(f"Loaded spectrogram: {spec.duration:.2f}s / C0-C10")

    def refresh_image(self) -> None:
        if self.spectrogram is None:
            return
        img = enhance_spectrogram(
            self.spectrogram.db,
            contrast=self.contrast,
            gamma=self.gamma,
            per_bin=self.enhance,
            harmonic_mode=self.harmonic_mode,
        ).T
        self.image.setImage(img, autoLevels=False, levels=(0.0, 1.0))
        try:
            cmap = pg.colormap.get(self.cmap)
            self.image.setLookupTable(cmap.getLookupTable(0.0, 1.0, 256))
        except Exception:
            pass

    def set_visual_options(self, *, contrast: float, gamma: float, enhance: bool, cmap: str, harmonic_mode: str = "off") -> None:
        self.contrast = contrast
        self.gamma = gamma
        self.enhance = enhance
        self.cmap = cmap
        self.harmonic_mode = harmonic_mode
        self.refresh_image()


    def set_beat_grid(self, *, enabled: bool, bpm: float, offset_sec: float) -> None:
        self.grid_enabled = bool(enabled)
        self.grid_bpm = max(1e-6, float(bpm))
        self.grid_offset_sec = float(offset_sec)
        self.redraw_beat_grid()

    def redraw_beat_grid(self) -> None:
        # 既存の目安線を消す
        for item in getattr(self, "_guide_items", []):
            try:
                self.plot.plotItem.removeItem(item)
            except Exception:
                pass
        self._guide_items = []

        if not getattr(self, "grid_enabled", False):
            return
        if self.spectrogram is None:
            return

        bpm = max(1e-6, float(getattr(self, "grid_bpm", 175.0)))
        offset = float(getattr(self, "grid_offset_sec", 0.0))
        duration = float(self.spectrogram.duration)
        period = 60.0 / bpm
        if period <= 0:
            return

        import math
        k0 = int(math.floor((0.0 - offset) / period))
        k1 = int(math.ceil((duration - offset) / period))

        # 線が多すぎると重いので最大5000本程度に間引く
        total = max(1, k1 - k0 + 1)
        step = max(1, int(math.ceil(total / 5000)))

        for k in range(k0, k1 + 1, step):
            t = offset + k * period
            if t < -1e-6 or t > duration + 1e-6:
                continue

            line = pg.InfiniteLine(pos=t, angle=90, movable=False)
            line.setZValue(5)

            if k % 4 == 0:
                line.setPen(pg.mkPen((255, 230, 120, 120), width=1))
            else:
                line.setPen(pg.mkPen((255, 255, 255, 55), width=1))

            self.plot.plotItem.addItem(line)
            self._guide_items.append(line)


    def set_view(self, start: float, window_sec: float, pitch_bottom: int, visible_notes: int) -> None:
        if self.spectrogram is None:
            return

        spec = self.spectrogram
        window_sec = max(0.2, min(float(window_sec), spec.duration))
        start = max(0.0, min(float(start), max(0.0, spec.duration - window_sec)))

        visible_notes = max(6, min(int(visible_notes), spec.midi_max - spec.midi_min + 1))
        pitch_bottom = max(spec.midi_min, min(int(pitch_bottom), spec.midi_max - visible_notes + 1))

        self.plot.setXRange(start, start + window_sec, padding=0)
        self.plot.setYRange(pitch_bottom - 0.5, pitch_bottom + visible_notes - 0.5, padding=0)

    def set_mode(self, mode: int) -> None:
        self.mode = int(mode) % 3
        if self.mode == 0:
            self.image.setOpacity(1.0)
        elif self.mode == 1:
            self.image.setOpacity(0.22)
        else:
            self.image.setOpacity(0.70)
        self.redraw_notes()

    def cycle_mode(self) -> None:
        self.set_mode(self.mode + 1)
        self.status_changed.emit(["Spectrogram Focus", "Note Focus", "Both"][self.mode])

    def set_playhead(self, seconds: float) -> None:
        if self.spectrogram is not None:
            seconds = max(0.0, min(float(seconds), self.spectrogram.duration))
        self._suppress_playhead = True
        self.playhead.setValue(seconds)
        self._suppress_playhead = False

    def playhead_time(self) -> float:
        return max(0.0, float(self.playhead.value()))

    def _on_playhead_moved(self) -> None:
        if self._suppress_playhead:
            return
        self.playhead_moved.emit(self.playhead_time())

    def set_notes(self, notes: list[Note]) -> None:
        self.notes = [n.normalized() for n in notes]
        self.selected_index = None
        self.selected_indices.clear()
        self.clear_undo()
        self.redraw_notes()
        self.notes_changed.emit()

    def set_snap_grid(self, *, enabled: bool, bpm: float, offset_sec: float, division: int = 1) -> None:
        self.snap_enabled = bool(enabled)
        self.snap_bpm = max(1e-6, float(bpm))
        self.snap_offset_sec = float(offset_sec)
        self.snap_division = max(1, int(division))

    def snap_time(self, seconds: float) -> float:
        if not self.snap_enabled:
            return max(0.0, float(seconds))

        step = 60.0 / max(1e-6, self.snap_bpm) / max(1, self.snap_division)
        if step <= 0:
            return max(0.0, float(seconds))

        offset = self.snap_offset_sec
        k = round((float(seconds) - offset) / step)
        t = offset + k * step

        if self.spectrogram is not None:
            t = max(0.0, min(t, self.spectrogram.duration))
        else:
            t = max(0.0, t)
        return t

    def add_note(self, start: float, end: float, midi: int) -> None:
        if self.spectrogram is not None:
            midi = max(self.spectrogram.midi_min, min(self.spectrogram.midi_max, midi))

        if self.snap_enabled:
            a = self.snap_time(start)
            b = self.snap_time(end)
            if abs(b - a) < 1e-9:
                # クリック気味の短いドラッグでも、最低1スナップ分の長さを確保
                step = 60.0 / max(1e-6, self.snap_bpm) / max(1, self.snap_division)
                if end >= start:
                    b = min((self.spectrogram.duration if self.spectrogram else a + step), a + step)
                else:
                    b = max(0.0, a - step)
            start, end = sorted((a, b))

        self.push_undo()
        self.notes.append(Note(start, end, midi).normalized())
        self.selected_index = len(self.notes) - 1
        self.selected_indices = {self.selected_index}
        self.redraw_notes()
        self.notes_changed.emit()
        snap = " snapped" if self.snap_enabled else ""
        self.status_changed.emit(f"Added{snap} {note_name(midi)} {start:.3f}-{end:.3f}s")

    def nearest_note_index(self, x: float, midi: int) -> int | None:
        """
        Hit-test only when the cursor directly touches the note rectangle.

        Previous versions used a wide nearest-note tolerance, which made empty
        clicks unexpectedly select/move nearby notes. Now:
          - time must be inside note start/end
          - pitch row must match exactly
        """
        eps = 1e-9
        candidates: list[tuple[float, int]] = []
        for i, n in enumerate(self.notes):
            if n.start - eps <= x <= n.end + eps and int(round(midi)) == int(round(n.midi)):
                # If overlapping notes exist on the same pitch, prefer the shorter one.
                candidates.append((n.duration, i))
        if not candidates:
            return None
        candidates.sort()
        return candidates[0][1]

    def select_nearest(self, x: float, midi: int, mods_value: int = 0) -> None:
        idx = self.nearest_note_index(x, midi)
        ctrl = bool(mods_value & int(QtCore.Qt.KeyboardModifier.ControlModifier.value))
        shift = bool(mods_value & int(QtCore.Qt.KeyboardModifier.ShiftModifier.value))

        if idx is not None:
            if ctrl:
                if idx in self.selected_indices:
                    self.selected_indices.remove(idx)
                else:
                    self.selected_indices.add(idx)
            elif shift and self.selected_index is not None:
                a, b = sorted((self.selected_index, idx))
                self.selected_indices.update(range(a, b + 1))
            else:
                self.selected_indices = {idx}

            self.selected_index = idx if self.selected_indices else None
            self.redraw_notes()

            if len(self.selected_indices) == 1:
                n = self.notes[next(iter(self.selected_indices))]
                self.status_changed.emit(f"Selected {note_name(n.midi)} {n.start:.3f}-{n.end:.3f}s")
            else:
                self.status_changed.emit(f"Selected {len(self.selected_indices)} notes")
            return

        if not ctrl:
            self.selected_index = None
            self.selected_indices.clear()
            self.redraw_notes()

        self.set_playhead(x)
        self.playhead_moved.emit(self.playhead_time())
        self.status_changed.emit(f"Playhead: {self.playhead_time():.3f}s")

    def delete_nearest(self, x: float, midi: int) -> None:
        idx = self.nearest_note_index(x, midi)
        if idx is not None:
            if idx in self.selected_indices and len(self.selected_indices) > 1:
                self.delete_selected()
                return

            self.push_undo()
            n = self.notes.pop(idx)
            self.selected_index = None
            self.selected_indices = {i - 1 if i > idx else i for i in self.selected_indices if i != idx}
            self.redraw_notes()
            self.notes_changed.emit()
            self.status_changed.emit(f"Deleted {note_name(n.midi)}")

    def delete_selected(self) -> None:
        if not self.selected_indices and self.selected_index is not None:
            self.selected_indices = {self.selected_index}

        if self.selected_index is not None:
            self.selected_indices.add(self.selected_index)

        valid = sorted((i for i in self.selected_indices if 0 <= i < len(self.notes)), reverse=True)
        if not valid:
            return

        self.push_undo()
        count = len(valid)
        for i in valid:
            self.notes.pop(i)

        self.selected_index = None
        self.selected_indices.clear()
        self.redraw_notes()
        self.notes_changed.emit()
        self.status_changed.emit(f"Deleted {count} note{'s' if count != 1 else ''}")

    def select_all_notes(self) -> None:
        self.selected_indices = set(range(len(self.notes)))
        self.selected_index = 0 if self.notes else None
        self.redraw_notes()
        self.status_changed.emit(f"Selected {len(self.selected_indices)} notes")

    def clear_selection(self) -> None:
        self.selected_index = None
        self.selected_indices.clear()
        self.redraw_notes()

    def set_selection_indices(self, indices) -> None:
        self.selected_indices = {int(i) for i in indices if 0 <= int(i) < len(self.notes)}
        self.selected_index = next(iter(self.selected_indices), None)
        self.redraw_notes()

    def redraw_notes(self) -> None:
        for item in self._note_items:
            self.plot.plotItem.removeItem(item)
        self._note_items.clear()

        alpha = 90 if self.mode == 0 else 220 if self.mode == 1 else 165
        for i, n in enumerate(self.notes):
            rect = QtWidgets.QGraphicsRectItem(QtCore.QRectF(n.start, n.midi - 0.45, n.duration, 0.9))
            rect.setZValue(20)
            if i in self.selected_indices:
                rect.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 255), 0.025))
                rect.setBrush(QtGui.QBrush(QtGui.QColor(255, 210, 80, min(255, alpha + 55))))
            else:
                rect.setPen(QtGui.QPen(QtGui.QColor(180, 230, 255, alpha), 0.015))
                rect.setBrush(QtGui.QBrush(QtGui.QColor(70, 190, 255, alpha)))
            self.plot.plotItem.addItem(rect)
            self._note_items.append(rect)
