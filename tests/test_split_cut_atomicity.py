from __future__ import annotations

import unittest
from unittest import mock

from core.note_model import Note
from web_ui import Bridge


class SplitCutAtomicityTests(unittest.TestCase):
    def make_bridge(self) -> Bridge:
        bridge = Bridge()
        bridge.settings["snapEnabled"] = False
        bridge.duration = 10.0
        bridge.notes = [
            Note(1.0, 4.0, 60.0).normalized(),
            Note(1.5, 4.5, 64.0).normalized(),
        ]
        bridge._saved_checkpoint = bridge._document_checkpoint()
        bridge._redo_stack.append(bridge._snapshot())
        return bridge

    def assert_failed_edit_unchanged(self, bridge: Bridge, original: list[Note]) -> None:
        self.assertEqual(bridge.notes, original)
        self.assertEqual(bridge.duration, 10.0)
        self.assertFalse(bridge._dirty)
        self.assertEqual(len(bridge._undo_stack), 0)
        self.assertEqual(len(bridge._redo_stack), 1)

    def test_split_failure_does_not_consume_redo(self):
        bridge = self.make_bridge()
        original = list(bridge.notes)
        split = bridge._split_note_exact
        calls = 0

        def fail_on_second(note: Note, at_time: float):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("simulated split failure")
            return split(note, at_time)

        with mock.patch.object(bridge, "_split_note_exact", side_effect=fail_on_second):
            with mock.patch.object(bridge, "_sync_notes_to_player") as sync:
                with self.assertRaisesRegex(RuntimeError, "simulated split failure"):
                    bridge.split_notes([0, 1], 2.0)
        self.assertEqual(calls, 2)
        self.assert_failed_edit_unchanged(bridge, original)
        sync.assert_not_called()

    def test_range_cut_failure_does_not_consume_redo(self):
        bridge = self.make_bridge()
        original = list(bridge.notes)
        split = bridge._split_note_exact
        calls = 0

        def fail_on_third(note: Note, at_time: float):
            nonlocal calls
            calls += 1
            if calls == 3:
                raise RuntimeError("simulated cut failure")
            return split(note, at_time)

        with mock.patch.object(bridge, "_split_note_exact", side_effect=fail_on_third):
            with mock.patch.object(bridge, "_sync_notes_to_player") as sync:
                with self.assertRaisesRegex(RuntimeError, "simulated cut failure"):
                    bridge.cut_notes_range([0, 1], 2.0, 3.0)
        self.assertEqual(calls, 3)
        self.assert_failed_edit_unchanged(bridge, original)
        sync.assert_not_called()

    def test_successful_split_records_one_undo_step(self):
        bridge = self.make_bridge()
        original = list(bridge.notes)
        with mock.patch.object(bridge, "_sync_notes_to_player") as sync:
            result = bridge.split_notes([0, 1], 2.0)
        self.assertEqual(result["indices"], [0, 1, 2, 3])
        self.assertEqual(len(bridge.notes), 4)
        self.assertEqual(len(bridge._undo_stack), 1)
        self.assertEqual(len(bridge._redo_stack), 0)
        self.assertTrue(bridge._dirty)
        sync.assert_called_once()
        with mock.patch.object(bridge, "_sync_notes_to_player"):
            bridge.undo()
        self.assertEqual(bridge.notes, original)
        self.assertFalse(bridge._dirty)

    def test_successful_range_cut_records_one_undo_step(self):
        bridge = self.make_bridge()
        original = list(bridge.notes)
        with mock.patch.object(bridge, "_sync_notes_to_player") as sync:
            result = bridge.cut_notes_range([0, 1], 2.0, 3.0)
        self.assertTrue(result["changed"])
        self.assertEqual(result["indices"], [0, 1, 2, 3])
        self.assertEqual(len(bridge.notes), 4)
        self.assertEqual(len(bridge._undo_stack), 1)
        self.assertEqual(len(bridge._redo_stack), 0)
        self.assertTrue(bridge._dirty)
        sync.assert_called_once()
        with mock.patch.object(bridge, "_sync_notes_to_player"):
            bridge.undo()
        self.assertEqual(bridge.notes, original)
        self.assertFalse(bridge._dirty)


if __name__ == "__main__":
    unittest.main()
