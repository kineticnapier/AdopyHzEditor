from __future__ import annotations

import unittest

from core.note_model import Note
from web_ui import Bridge


class HarmonicMidiBoundsTests(unittest.TestCase):
    def test_out_of_range_harmonic_insert_is_rejected_without_history_or_dirty(self):
        bridge = Bridge()
        bridge.notes = [Note(0.0, 0.5, 60.0).normalized()]
        bridge._dirty = False
        bridge._undo_stack.clear()
        options = {
            "rootHz": 20_000.0,
            "rootShift": "1",
            "base1dOffset": 0,
            "harmonics": "3",
            "timeUnit": "seconds",
            "bpm": 120.0,
            "start": 1.0,
            "duration": 0.5,
            "edo": 41,
            "offset": 2,
        }

        preview = bridge.preview_harmonic_diagram(options)
        self.assertGreater(preview["rows"][0]["midi"], 127.0)

        with self.assertRaisesRegex(ValueError, "MIDI範囲外"):
            bridge.insert_harmonic_diagram(options)

        self.assertEqual(len(bridge.notes), 1)
        self.assertEqual(len(bridge._undo_stack), 0)
        self.assertFalse(bridge._dirty)

    def test_in_range_harmonic_insert_still_creates_note(self):
        bridge = Bridge()
        options = {
            "rootHz": 440.0,
            "rootShift": "1",
            "base1dOffset": 0,
            "harmonics": "1",
            "timeUnit": "seconds",
            "bpm": 120.0,
            "start": 1.0,
            "duration": 0.5,
            "edo": 41,
            "offset": 2,
        }

        result = bridge.insert_harmonic_diagram(options)

        self.assertEqual(result["indices"], [0])
        self.assertAlmostEqual(bridge.notes[0].midi, 69.0)
        self.assertTrue(bridge._dirty)


if __name__ == "__main__":
    unittest.main()
