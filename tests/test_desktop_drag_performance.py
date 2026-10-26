from __future__ import annotations

import unittest

from core.note_model import Note
from desktop.editor_view import EditorView


class _Item:
    def __init__(self):
        self.positions = []

    def setPos(self, x, y):
        self.positions.append((x, y))


class DesktopDragPerformanceTests(unittest.TestCase):
    def test_drag_preview_updates_only_selected_graphics_without_full_redraw(self):
        first, second = _Item(), _Item()

        class Dummy:
            _move_active = True
            _move_original_notes = [(1, Note(1, 2, 60))]
            notes = [Note(0, .5, 50), Note(1, 2, 60)]
            _note_item_groups = [[first], [second]]
            _last_move_dx = 0.0
            _last_move_dy = 0
            redraws = 0

            @staticmethod
            def _clamp_move_delta(dx, dy):
                return dx, dy

            def redraw_notes(self):
                self.redraws += 1

        dummy = Dummy()
        EditorView.preview_move_selected(dummy, 0.75, 2)
        self.assertEqual(first.positions, [])
        self.assertEqual(second.positions, [(0.75, 2.0)])
        self.assertEqual(dummy.redraws, 0)
        self.assertEqual(dummy.notes[1].start, 1.75)

    def test_curve_move_bounds_include_control_points_and_not_analysis_range(self):
        class Dummy:
            _move_original_notes = [(0, Note(1, 2, 120, kind="curve", midi_end=125, ctrl1_midi=126, ctrl2_midi=124))]
            spectrogram = type("Spec", (), {"duration": 10.0, "midi_min": 60, "midi_max": 72})()
            snap_enabled = False

        dx, dy = EditorView._clamp_move_delta(Dummy(), 1.0, 50)
        self.assertEqual(dx, 1.0)
        self.assertEqual(dy, 1)


if __name__ == "__main__":
    unittest.main()
