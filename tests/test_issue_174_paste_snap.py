from __future__ import annotations

import unittest

from core.note_model import Note
from web_ui import Bridge


class PasteSnapTests(unittest.TestCase):
    def _bridge(self) -> Bridge:
        bridge = Bridge()
        bridge.duration = 5.0
        bridge.settings["bpm"] = 120.0
        bridge.settings["snapDiv"] = 1
        bridge.settings["offsetMs"] = 0.0
        bridge._clipboard = [
            Note(0.0, 0.2, 60.0).normalized(),
            Note(0.3, 0.4, 64.0).normalized(),
        ]
        return bridge

    def test_enabled_snap_moves_paste_anchor_to_grid_and_keeps_spacing(self):
        bridge = self._bridge()
        bridge.settings["snapEnabled"] = True

        result = bridge.paste_notes(1.31)

        self.assertTrue(result["changed"])
        self.assertAlmostEqual(bridge.notes[0].start, 1.5)
        self.assertAlmostEqual(bridge.notes[1].start, 1.8)
        self.assertAlmostEqual(
            bridge.notes[1].start - bridge.notes[0].start,
            0.3,
        )

    def test_disabled_snap_keeps_free_paste_position(self):
        bridge = self._bridge()
        bridge.settings["snapEnabled"] = False

        bridge.paste_notes(1.31)

        self.assertAlmostEqual(bridge.notes[0].start, 1.31)
        self.assertAlmostEqual(bridge.notes[1].start, 1.61)

    def test_offset_grid_is_respected(self):
        bridge = self._bridge()
        bridge.settings["snapEnabled"] = True
        bridge.settings["offsetMs"] = 100.0

        bridge.paste_notes(1.31)

        self.assertAlmostEqual(bridge.notes[0].start, 1.1)

    def test_end_clamp_uses_latest_grid_that_keeps_clipboard_in_chart(self):
        bridge = self._bridge()
        bridge.duration = 1.0
        bridge.settings["snapEnabled"] = True

        bridge.paste_notes(0.99)

        self.assertAlmostEqual(bridge.notes[0].start, 0.5)
        self.assertLessEqual(max(note.end for note in bridge.notes), 1.0)


if __name__ == "__main__":
    unittest.main()
