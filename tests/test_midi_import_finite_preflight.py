from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest import mock

from core.note_model import Note
import web.io as web_io
from web_ui import Bridge


class MidiImportFinitePreflightTests(unittest.TestCase):
    def make_bridge(self) -> Bridge:
        bridge = Bridge()
        bridge.notes = [Note(1.0, 2.0, 60.0).normalized()]
        bridge.duration = 10.0
        bridge._saved_checkpoint = bridge._document_checkpoint()
        bridge._redo_stack.append(bridge._snapshot())
        return bridge

    def test_non_finite_midi_note_preserves_document_and_history(self):
        invalid_notes = (
            Note(float("nan"), 2.0, 60.0),
            Note(1.0, float("inf"), 60.0),
            Note(1.0, 2.0, float("nan")),
            Note(1.0, 2.0, 60.0, kind="curve", midi_end=float("inf")),
            Note(1.0, 2.0, 60.0, kind="curve", ctrl1_midi=float("nan")),
            Note(1.0, 2.0, 60.0, kind="curve", ctrl2_midi=float("-inf")),
            Note(1.0, 2.0, 60.0, target_angle=float("nan")),
        )
        for invalid_note in invalid_notes:
            with self.subTest(note=invalid_note):
                bridge = self.make_bridge()
                before = bridge._document_checkpoint()
                with (
                    mock.patch.object(bridge, "_dialog", return_value="bad.mid"),
                    mock.patch.object(
                        web_io, "import_midi",
                        return_value=SimpleNamespace(notes=[Note(3.0, 4.0, 70.0), invalid_note]),
                    ),
                    mock.patch.object(bridge, "_sync_notes_to_player") as sync,
                ):
                    with self.assertRaisesRegex(ValueError, "MIDI import contains"):
                        bridge.import_midi_dialog()
                self.assertEqual(bridge._document_checkpoint(), before)
                self.assertEqual(bridge.duration, 10.0)
                self.assertEqual(len(bridge._undo_stack), 0)
                self.assertEqual(len(bridge._redo_stack), 1)
                self.assertFalse(bridge._dirty)
                sync.assert_not_called()

    def test_valid_midi_import_remains_undoable(self):
        bridge = self.make_bridge()
        with (
            mock.patch.object(bridge, "_dialog", return_value="valid.mid"),
            mock.patch.object(
                web_io, "import_midi",
                return_value=SimpleNamespace(notes=[Note(3.0, 4.0, 70.0)]),
            ),
        ):
            bridge.import_midi_dialog()
        self.assertEqual(len(bridge.notes), 2)
        self.assertEqual(len(bridge._undo_stack), 1)
        self.assertEqual(len(bridge._redo_stack), 0)
        self.assertTrue(bridge._dirty)


if __name__ == "__main__":
    unittest.main()
