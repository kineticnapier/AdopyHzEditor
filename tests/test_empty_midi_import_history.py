from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest import mock

from core.note_model import Note
import web.io as web_io
from web_ui import Bridge


class EmptyMidiImportHistoryTests(unittest.TestCase):
    def make_bridge(self) -> Bridge:
        bridge = Bridge()
        bridge.notes = [Note(1.0, 2.0, 60.0).normalized()]
        bridge.duration = 10.0
        bridge._saved_checkpoint = bridge._document_checkpoint()
        bridge._redo_stack.append(bridge._snapshot())
        return bridge

    def test_empty_import_preserves_clean_document_and_redo(self):
        bridge = self.make_bridge()
        before = bridge._document_checkpoint()
        with (
            mock.patch.object(bridge, "_dialog", return_value="empty.mid"),
            mock.patch.object(web_io, "import_midi", return_value=SimpleNamespace(notes=[])),
            mock.patch.object(bridge, "_sync_notes_to_player") as sync,
        ):
            result = bridge.import_midi_dialog()

        self.assertEqual(bridge._document_checkpoint(), before)
        self.assertEqual(len(bridge._undo_stack), 0)
        self.assertEqual(len(bridge._redo_stack), 1)
        self.assertFalse(bridge._dirty)
        self.assertFalse(result["dirty"])
        self.assertIn("ノートがありません", result["status"])
        sync.assert_not_called()

    def test_empty_import_preserves_existing_dirty_state_and_history(self):
        bridge = self.make_bridge()
        bridge._dirty = True
        bridge._undo_stack.append(bridge._snapshot())
        before = bridge._document_checkpoint()
        with (
            mock.patch.object(bridge, "_dialog", return_value="empty.mid"),
            mock.patch.object(web_io, "import_midi", return_value=SimpleNamespace(notes=[])),
            mock.patch.object(bridge, "_sync_notes_to_player") as sync,
        ):
            result = bridge.import_midi_dialog()

        self.assertEqual(bridge._document_checkpoint(), before)
        self.assertEqual(len(bridge._undo_stack), 1)
        self.assertEqual(len(bridge._redo_stack), 1)
        self.assertTrue(bridge._dirty)
        self.assertTrue(result["dirty"])
        sync.assert_not_called()


if __name__ == "__main__":
    unittest.main()
