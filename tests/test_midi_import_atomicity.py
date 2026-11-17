from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest import mock

from core.note_model import Note
import web.io as web_io
from web_ui import Bridge


class MidiImportAtomicityTests(unittest.TestCase):
    def make_bridge(self) -> Bridge:
        bridge = Bridge()
        bridge.notes = [Note(1.0, 2.0, 60.0).normalized()]
        bridge.duration = 10.0
        bridge._saved_checkpoint = bridge._document_checkpoint()
        bridge._redo_stack.append(bridge._snapshot())
        return bridge

    def test_later_invalid_note_preserves_document_and_history(self):
        bridge = self.make_bridge()
        before = bridge._document_checkpoint()
        invalid_note = mock.Mock()
        invalid_note.normalized.side_effect = ValueError("invalid MIDI note")
        with (
            mock.patch.object(bridge, "_dialog", return_value="broken.mid"),
            mock.patch.object(
                web_io,
                "import_midi",
                return_value=SimpleNamespace(
                    notes=[Note(3.0, 4.0, 64.0), invalid_note]
                ),
            ),
            mock.patch.object(bridge, "_sync_notes_to_player") as sync,
        ):
            with self.assertRaisesRegex(ValueError, "invalid MIDI note"):
                bridge.import_midi_dialog()

        self.assertEqual(bridge._document_checkpoint(), before)
        self.assertEqual(len(bridge._undo_stack), 0)
        self.assertEqual(len(bridge._redo_stack), 1)
        self.assertFalse(bridge._dirty)
        sync.assert_not_called()

    def test_successful_import_sorts_notes_and_undo_restores_duration(self):
        bridge = self.make_bridge()
        original = bridge._document_checkpoint()
        imported = [Note(12.0, 14.0, 72.0), Note(0.0, 0.5, 48.0)]
        with (
            mock.patch.object(bridge, "_dialog", return_value="notes.mid"),
            mock.patch.object(
                web_io, "import_midi", return_value=SimpleNamespace(notes=imported)
            ),
            mock.patch.object(bridge, "_sync_notes_to_player"),
        ):
            result = bridge.import_midi_dialog()
            self.assertTrue(result["dirty"])
            self.assertEqual([n.start for n in bridge.notes], [0.0, 1.0, 12.0])
            self.assertEqual(bridge.duration, 14.0)
            self.assertEqual(len(bridge._undo_stack), 1)
            self.assertEqual(len(bridge._redo_stack), 0)

            bridge.undo()
            self.assertEqual(bridge._document_checkpoint(), original)
            self.assertFalse(bridge._dirty)
            self.assertEqual(bridge.duration, 10.0)

            bridge.redo()
            self.assertEqual([n.start for n in bridge.notes], [0.0, 1.0, 12.0])
            self.assertEqual(bridge.duration, 14.0)
            self.assertTrue(bridge._dirty)


if __name__ == "__main__":
    unittest.main()
