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

    def test_fit_view_without_notes_remains_valid(self):
        bridge = Bridge()
        bridge.duration = 5.0
        bridge.notes = []
        view = bridge.fit_view()
        self.assertEqual(view["start"], 0.0)
        self.assertEqual(view["windowSeconds"], 5.0)


if __name__ == "__main__":
    unittest.main()
