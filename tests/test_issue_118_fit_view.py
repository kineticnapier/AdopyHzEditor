from __future__ import annotations

import unittest

from core.note_model import Note
from web.backend import Bridge


class FitViewRegressionTests(unittest.TestCase):
    def test_fit_view_covers_fixed_and_curve_note_bounds(self):
        bridge = Bridge()
        bridge.duration = 20.0
        bridge.notes = [
            Note(2.0, 3.0, 48.0),
            Note(10.0, 14.0, 72.0, kind="curve", midi_end=84.0, ctrl1_midi=40.0, ctrl2_midi=96.0),
        ]

        view = bridge.fit_view()

        self.assertLessEqual(view["start"], 2.0)
        self.assertGreaterEqual(view["start"] + view["windowSeconds"], 14.0)
        self.assertLessEqual(view["pitchBottom"], 40)
        self.assertGreaterEqual(view["pitchBottom"] + view["visibleNotes"], 96)

    def test_fit_view_near_top_midi_keeps_padding_inside_valid_range(self):
        bridge = Bridge()
        bridge.duration = 10.0
        bridge.notes = [Note(1.0, 2.0, 127.0).normalized()]

        view = bridge.fit_view()

        self.assertGreaterEqual(view["pitchBottom"], 0)
        self.assertGreaterEqual(view["visibleNotes"], 6)
        self.assertLessEqual(view["pitchBottom"] + view["visibleNotes"], 128)
        self.assertLessEqual(view["pitchBottom"], 127)
        self.assertGreater(view["pitchBottom"] + view["visibleNotes"], 127)

    def test_fit_view_full_midi_span_does_not_overflow(self):
        bridge = Bridge()
        bridge.duration = 10.0
        bridge.notes = [
            Note(1.0, 2.0, 0.0).normalized(),
            Note(3.0, 4.0, 127.0).normalized(),
        ]

        view = bridge.fit_view()

        self.assertEqual(view["pitchBottom"], 0)
        self.assertEqual(view["visibleNotes"], 128)
        self.assertEqual(view["pitchBottom"] + view["visibleNotes"], 128)

    def test_fit_view_without_notes_remains_valid(self):
        bridge = Bridge()
        bridge.duration = 5.0
        bridge.notes = []
        view = bridge.fit_view()
        self.assertEqual(view["start"], 0.0)
        self.assertEqual(view["windowSeconds"], 5.0)


if __name__ == "__main__":
    unittest.main()
