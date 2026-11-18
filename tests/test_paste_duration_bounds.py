from __future__ import annotations

import unittest

from core.note_model import Note
from web_ui import Bridge


class PasteDurationBoundsTests(unittest.TestCase):
    def test_oversized_clipboard_extends_chart_and_preserves_requested_position(self):
        bridge = Bridge()
        bridge.duration = 2.0
        bridge.notes = []
        bridge._clipboard = [Note(0.0, 3.0, 60.0).normalized()]
        bridge._saved_checkpoint = bridge._document_checkpoint()

        result = bridge.paste_notes(1.0)

        self.assertIs(result["changed"], True)
        self.assertEqual(result["indices"], [0])
        self.assertEqual((bridge.notes[0].start, bridge.notes[0].end), (1.0, 4.0))
        self.assertEqual(bridge.duration, 4.0)
        self.assertTrue(bridge._dirty)
        self.assertEqual(len(bridge._undo_stack), 1)
        self.assertGreaterEqual(bridge.player.duration, 4.0)

        bridge.undo()
        self.assertEqual(bridge.notes, [])
        self.assertEqual(bridge.duration, 2.0)
        self.assertFalse(bridge._dirty)

        bridge.redo()
        self.assertEqual((bridge.notes[0].start, bridge.notes[0].end), (1.0, 4.0))
        self.assertEqual(bridge.duration, 4.0)
        self.assertTrue(bridge._dirty)

    def test_oversized_clipboard_respects_snap_and_extends_duration(self):
        bridge = Bridge()
        bridge.duration = 2.0
        bridge._clipboard = [Note(0.0, 3.0, 64.0).normalized()]
        bridge.settings.update(snapEnabled=True, bpm=120.0, snapDiv=1, offsetMs=0.0)

        result = bridge.paste_notes(1.1)

        self.assertEqual(result["indices"], [0])
        self.assertAlmostEqual(bridge.notes[0].start, 1.0)
        self.assertAlmostEqual(bridge.notes[0].end, 4.0)
        self.assertAlmostEqual(bridge.duration, 4.0)

    def test_fitting_clipboard_keeps_existing_end_clamp(self):
        bridge = Bridge()
        bridge.duration = 10.0
        bridge._clipboard = [
            Note(0.0, 1.0, 60.0).normalized(),
            Note(2.0, 3.0, 64.0).normalized(),
        ]

        result = bridge.paste_notes(9.0)

        pasted = [bridge.notes[i] for i in result["indices"]]
        self.assertEqual([(n.start, n.end) for n in pasted], [(7.0, 8.0), (9.0, 10.0)])
        self.assertEqual(bridge.duration, 10.0)


if __name__ == "__main__":
    unittest.main()
