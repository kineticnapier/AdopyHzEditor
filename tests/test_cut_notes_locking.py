from __future__ import annotations

import threading
import unittest
from unittest import mock

from core.note_model import Note
from web_ui import Bridge


class CutNotesLockingTests(unittest.TestCase):
    def make_bridge(self) -> Bridge:
        bridge = Bridge()
        bridge.duration = 10.0
        bridge.notes = [
            Note(1.0, 2.0, 60.0).normalized(),
            Note(3.0, 4.0, 64.0).normalized(),
        ]
        bridge._saved_checkpoint = bridge._document_checkpoint()
        return bridge

    def test_cut_holds_lock_between_clipboard_copy_and_note_deletion(self):
        bridge = self.make_bridge()
        copied = threading.Event()
        release_copy = threading.Event()
        delete_started = threading.Event()
        delete_finished = threading.Event()
        errors: list[BaseException] = []
        results: dict[str, dict] = {}
        original_copy = bridge.copy_notes

        def paused_copy(indices: list[int]) -> dict:
            result = original_copy(indices)
            copied.set()
            if not release_copy.wait(timeout=3):
                raise TimeoutError("cut copy was not released")
            return result

        def cut() -> None:
            try:
                results["cut"] = bridge.cut_notes([1])
            except BaseException as error:
                errors.append(error)

        def competing_delete() -> None:
            delete_started.set()
            try:
                results["delete"] = bridge.delete_notes([0])
            except BaseException as error:
                errors.append(error)
            finally:
                delete_finished.set()

        cut_thread = threading.Thread(target=cut)
        delete_thread = threading.Thread(target=competing_delete)
        with mock.patch.object(bridge, "copy_notes", side_effect=paused_copy):
            cut_thread.start()
            try:
                self.assertTrue(copied.wait(timeout=2), "cut did not reach clipboard copy")
                delete_thread.start()
                self.assertTrue(delete_started.wait(timeout=2))
                # Another request cannot remove note 0 while the cut is paused
                # after copying note 1; otherwise the cut's index becomes stale.
                self.assertFalse(delete_finished.wait(timeout=0.15))
            finally:
                release_copy.set()
                cut_thread.join(timeout=3)
                if delete_thread.ident is not None:
                    delete_thread.join(timeout=3)

        self.assertFalse(cut_thread.is_alive())
        self.assertFalse(delete_thread.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(bridge.notes, [])
        self.assertEqual(len(bridge._clipboard), 1)
        self.assertEqual(bridge._clipboard[0].midi, 64.0)
        self.assertEqual(len(bridge._undo_stack), 2)
        self.assertNotEqual(results["cut"].get("changed"), False)

    def test_invalid_cut_preserves_existing_clipboard_and_history(self):
        bridge = self.make_bridge()
        bridge.copy_notes([0])
        clipboard_before = list(bridge._clipboard)
        notes_before = list(bridge.notes)
        result = bridge.cut_notes([999])
        self.assertIs(result["changed"], False)
        self.assertEqual(bridge.notes, notes_before)
        self.assertEqual(bridge._clipboard, clipboard_before)
        self.assertEqual(len(bridge._undo_stack), 0)
        self.assertFalse(bridge._dirty)


if __name__ == "__main__":
    unittest.main()
