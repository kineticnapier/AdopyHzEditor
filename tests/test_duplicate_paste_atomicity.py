from __future__ import annotations

import unittest
from unittest import mock

from core.note_model import Note
from web_ui import Bridge


class DuplicatePasteAtomicityTests(unittest.TestCase):
    def make_bridge(self) -> Bridge:
        b = Bridge()
        b.settings["snapEnabled"] = False
        b.duration = 10.0
        b.notes = [Note(1, 1.5, 60).normalized(), Note(2, 2.5, 64).normalized()]
        b._clipboard = [Note(0, 1, 67).normalized(), Note(1, 2, 69).normalized()]
        b._saved_checkpoint = b._document_checkpoint()
        b._redo_stack.append(b._snapshot())
        return b

    def assert_failure_is_atomic(self, method_name: str, operation) -> None:
        b = self.make_bridge()
        original_notes = list(b.notes)
        original_method = getattr(Note, method_name)
        calls = 0

        def fail_second(note, *args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("simulated second-note failure")
            return original_method(note, *args, **kwargs)

        with mock.patch.object(Note, method_name, autospec=True, side_effect=fail_second):
            with mock.patch.object(b, "_sync_notes_to_player") as sync:
                with self.assertRaisesRegex(RuntimeError, "second-note failure"):
                    operation(b)
        self.assertEqual(calls, 2)
        self.assertEqual(b.notes, original_notes)
        self.assertEqual(b.duration, 10.0)
        self.assertFalse(b._dirty)
        self.assertEqual(len(b._undo_stack), 0)
        self.assertEqual(len(b._redo_stack), 1)
        sync.assert_not_called()

    def test_duplicate_failure_preserves_notes_and_redo(self):
        self.assert_failure_is_atomic(
            "with_time_offset", lambda b: b.duplicate_notes([0, 1])
        )

    def test_shifted_duplicate_failure_preserves_notes_and_redo(self):
        self.assert_failure_is_atomic(
            "shifted", lambda b: b.duplicate_notes_shifted([0, 1], 0.5, 1.0)
        )

    def test_paste_failure_preserves_notes_and_redo(self):
        self.assert_failure_is_atomic(
            "with_time_offset", lambda b: b.paste_notes(4.0)
        )

    def test_successful_operations_create_one_undo_step(self):
        operations = (
            lambda b: b.duplicate_notes([0, 1]),
            lambda b: b.duplicate_notes_shifted([0, 1], 0.5, 1.0),
            lambda b: b.paste_notes(4.0),
        )
        for operation in operations:
            with self.subTest(operation=operation):
                b = self.make_bridge()
                before = list(b.notes)
                with mock.patch.object(b, "_sync_notes_to_player") as sync:
                    result = operation(b)
                self.assertEqual(result["indices"], [2, 3])
                self.assertEqual(len(b.notes), 4)
                self.assertTrue(b._dirty)
                self.assertEqual(len(b._undo_stack), 1)
                self.assertEqual(len(b._redo_stack), 0)
                sync.assert_called_once()
                with mock.patch.object(b, "_sync_notes_to_player"):
                    b.undo()
                self.assertEqual(b.notes, before)
                self.assertEqual(b.duration, 10.0)
                self.assertFalse(b._dirty)


if __name__ == "__main__":
    unittest.main()
