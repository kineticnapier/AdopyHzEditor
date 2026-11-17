from __future__ import annotations

import unittest
from unittest import mock

from core.note_model import Note
from web_ui import Bridge


class NotePropertyNoopHistoryTests(unittest.TestCase):
    def make_bridge(self, note: Note | None = None) -> Bridge:
        bridge = Bridge()
        bridge.duration = 10.0
        bridge.notes = [(note or Note(1.0, 2.0, 60.0)).normalized()]
        bridge._saved_checkpoint = bridge._document_checkpoint()
        bridge._redo_stack.append(bridge._snapshot())
        return bridge

    def assert_unchanged(self, bridge: Bridge, result: dict) -> None:
        self.assertIs(result["changed"], False)
        self.assertFalse(bridge._dirty)
        self.assertEqual(len(bridge._undo_stack), 0)
        self.assertEqual(len(bridge._redo_stack), 1)

    def test_inspector_noop_preserves_redo_and_does_not_sync_audio(self):
        for changes in ({}, {"start": 1.0, "end": 2.0}, {"midi": 60.0}, {"velocity": 100}):
            with self.subTest(changes=changes):
                bridge = self.make_bridge()
                with mock.patch.object(bridge, "_sync_notes_to_player") as sync:
                    result = bridge.set_note_properties(0, changes)
                self.assert_unchanged(bridge, result)
                self.assertEqual(result["index"], 0)
                sync.assert_not_called()

    def test_inspector_real_change_creates_one_undo_step(self):
        bridge = self.make_bridge()
        result = bridge.set_note_properties(0, {"midi": 65.0})
        self.assertIs(result["changed"], True)
        self.assertEqual(bridge.notes[0].midi, 65.0)
        self.assertTrue(bridge._dirty)
        self.assertEqual(len(bridge._undo_stack), 1)
        self.assertEqual(len(bridge._redo_stack), 0)
        bridge.undo()
        self.assertEqual(bridge.notes[0].midi, 60.0)
        self.assertFalse(bridge._dirty)

    def test_reapplying_same_curve_interpolation_preserves_redo(self):
        note = Note(1.0, 2.0, 60.0, kind="curve", midi_end=64.0,
                    ctrl1_midi=61.0, ctrl2_midi=63.0, interpolation="linear")
        bridge = self.make_bridge(note)
        with mock.patch.object(bridge, "_sync_notes_to_player") as sync:
            result = bridge.apply_interpolation([0], "linear")
        self.assert_unchanged(bridge, result)
        sync.assert_not_called()
        changed = bridge.apply_interpolation([0], "ease_in")
        self.assertIs(changed["changed"], True)
        self.assertEqual(len(bridge._undo_stack), 1)

    def test_reapplying_same_target_angle_preserves_redo(self):
        bridge = self.make_bridge(Note(1.0, 2.0, 60.0).with_target_angle(45.0))
        result = bridge.apply_target_angle([0], 45.0)
        self.assert_unchanged(bridge, result)

    def test_clearing_already_empty_target_angle_preserves_redo(self):
        bridge = self.make_bridge()
        result = bridge.clear_target_angle([0])
        self.assert_unchanged(bridge, result)
        changed = bridge.apply_target_angle([0], 45.0)
        self.assertIs(changed["changed"], True)
        self.assertEqual(len(bridge._undo_stack), 1)
        cleared = bridge.clear_target_angle([0])
        self.assertIs(cleared["changed"], True)
        self.assertEqual(len(bridge._undo_stack), 2)


if __name__ == "__main__":
    unittest.main()
