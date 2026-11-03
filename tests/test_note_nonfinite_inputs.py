from __future__ import annotations

import math
import unittest
from unittest import mock

from core.note_model import Note
from web.notes import _clamp
from web_ui import Bridge


class NonFiniteNoteInputTests(unittest.TestCase):
    def make_bridge(self) -> Bridge:
        bridge = Bridge()
        bridge.duration = 10.0
        bridge.notes = [Note(1.0, 2.0, 60.0).normalized()]
        bridge._clipboard = [Note(0.0, 1.0, 64.0).normalized()]
        bridge._saved_checkpoint = bridge._document_checkpoint()
        bridge._redo_stack.append(bridge._snapshot())
        return bridge

    def assert_unchanged(self, bridge: Bridge, original: list[Note]) -> None:
        self.assertEqual(bridge.notes, original)
        self.assertEqual(bridge.duration, 10.0)
        self.assertFalse(bridge._dirty)
        self.assertEqual(len(bridge._undo_stack), 0)
        self.assertEqual(len(bridge._redo_stack), 1)

    def test_inspector_rejects_nonfinite_time_and_pitch(self):
        for field in ("start", "end", "midi"):
            for value in (math.nan, math.inf, -math.inf):
                with self.subTest(field=field, value=value):
                    bridge = self.make_bridge()
                    original = list(bridge.notes)
                    with mock.patch.object(bridge, "_sync_notes_to_player") as sync:
                        with self.assertRaisesRegex(ValueError, "finite"):
                            bridge.set_note_properties(0, {field: value})
                    self.assert_unchanged(bridge, original)
                    sync.assert_not_called()

    def test_move_rejects_nonfinite_time_and_pitch_deltas(self):
        for field in ("dx", "dy"):
            for value in (math.nan, math.inf, -math.inf):
                with self.subTest(field=field, value=value):
                    bridge = self.make_bridge()
                    original = list(bridge.notes)
                    args = {"dx": 0.0, "dy": 0.0}
                    args[field] = value
                    with mock.patch.object(bridge, "_sync_notes_to_player") as sync:
                        with self.assertRaisesRegex(ValueError, "finite"):
                            bridge.move_notes([0], **args)
                    self.assert_unchanged(bridge, original)
                    sync.assert_not_called()

    def test_paste_rejects_nonfinite_insertion_time(self):
        for value in (math.nan, math.inf, -math.inf):
            with self.subTest(value=value):
                bridge = self.make_bridge()
                original = list(bridge.notes)
                with mock.patch.object(bridge, "_sync_notes_to_player") as sync:
                    with self.assertRaisesRegex(ValueError, "finite"):
                        bridge.paste_notes(value)
                self.assert_unchanged(bridge, original)
                sync.assert_not_called()

    def test_add_rejects_nonfinite_time_and_pitch(self):
        for field in ("start", "end", "midi"):
            for value in (math.nan, math.inf, -math.inf):
                with self.subTest(field=field, value=value):
                    bridge = self.make_bridge()
                    original = list(bridge.notes)
                    args = {"start": 1.0, "end": 2.0, "midi": 60.0}
                    args[field] = value
                    with mock.patch.object(bridge, "_sync_notes_to_player") as sync:
                        with self.assertRaisesRegex(ValueError, "finite"):
                            bridge.add_note(**args)
                    self.assert_unchanged(bridge, original)
                    sync.assert_not_called()

    def test_finite_bounds_still_clamp(self):
        self.assertEqual(_clamp(-5.0, 0.0, 10.0), 0.0)
        self.assertEqual(_clamp(5.5, 0.0, 10.0), 5.5)
        self.assertEqual(_clamp(50.0, 0.0, 10.0), 10.0)


if __name__ == "__main__":
    unittest.main()
