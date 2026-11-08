from __future__ import annotations

import unittest
from unittest import mock

from core.note_model import Note
from web_ui import Bridge


class NoteNoopChangedContractTests(unittest.TestCase):
    def make_bridge(self) -> Bridge:
        bridge = Bridge()
        bridge.settings["snapEnabled"] = False
        bridge.duration = 10.0
        bridge.notes = [
            Note(1.0, 2.0, 60.0).normalized(),
            Note(3.0, 4.0, 64.0).normalized(),
        ]
        bridge._saved_checkpoint = bridge._document_checkpoint()
        bridge._redo_stack.append(bridge._snapshot())
        return bridge

    def assert_noop(self, operation) -> None:
        bridge = self.make_bridge()
        before = list(bridge.notes)
        with mock.patch.object(bridge, "_sync_notes_to_player") as sync:
            result = operation(bridge)
        # App.applyMutation treats missing changed as a successful edit.
        self.assertIs(result.get("changed"), False)
        self.assertEqual(bridge.notes, before)
        self.assertFalse(bridge._dirty)
        self.assertEqual(len(bridge._undo_stack), 0)
        self.assertEqual(len(bridge._redo_stack), 1)
        sync.assert_not_called()

    def test_invalid_selection_does_not_report_an_edit(self):
        operations = {
            "delete": lambda b: b.delete_notes([99]),
            "cut": lambda b: b.cut_notes([99]),
            "move": lambda b: b.move_notes([99], 1.0, 0.0),
            "resize": lambda b: b.resize_notes([99], "end", 1.0),
            "quantize": lambda b: b.quantize_notes([99]),
            "interpolation": lambda b: b.apply_interpolation([99]),
            "target_angle": lambda b: b.apply_target_angle([99], 30.0),
            "clear_target_angle": lambda b: b.clear_target_angle([99]),
            "inspector": lambda b: b.set_note_properties(99, {"velocity": 88}),
            "split": lambda b: b.split_notes([99], 1.5),
            "shifted_duplicate": lambda b: b.duplicate_notes_shifted([99], 1.0, 0.0),
            "bulk_edit": lambda b: b.bulk_edit_notes([99], {"timeDelta": 1.0}),
        }
        for name, operation in operations.items():
            with self.subTest(operation=name):
                self.assert_noop(operation)

    def test_split_outside_selected_notes_does_not_report_an_edit(self):
        self.assert_noop(lambda b: b.split_notes([0], 5.0))

    def test_inspector_rejects_noninteger_indices_without_touching_history(self):
        import math

        for index in (0.5, math.nan, math.inf, -math.inf, True, "0", None, -1, 99):
            with self.subTest(index=index):
                self.assert_noop(
                    lambda b, value=index: b.set_note_properties(value, {"velocity": 88})
                )

    def test_inspector_accepts_integer_valued_float_index(self):
        bridge = self.make_bridge()
        with mock.patch.object(bridge, "_sync_notes_to_player") as sync:
            result = bridge.set_note_properties(0.0, {"velocity": 88})
        self.assertIs(result["changed"], True)
        self.assertEqual(bridge.notes[0].velocity, 88)
        self.assertTrue(bridge._dirty)
        self.assertEqual(len(bridge._undo_stack), 1)
        self.assertEqual(len(bridge._redo_stack), 0)
        sync.assert_called_once()

    def test_valid_split_still_creates_one_undo_step(self):
        bridge = self.make_bridge()
        with mock.patch.object(bridge, "_sync_notes_to_player") as sync:
            result = bridge.split_notes([0], 1.5)
        self.assertNotEqual(result.get("changed"), False)
        self.assertEqual(len(bridge.notes), 3)
        self.assertTrue(bridge._dirty)
        self.assertEqual(len(bridge._undo_stack), 1)
        self.assertEqual(len(bridge._redo_stack), 0)
        sync.assert_called_once()


if __name__ == "__main__":
    unittest.main()
