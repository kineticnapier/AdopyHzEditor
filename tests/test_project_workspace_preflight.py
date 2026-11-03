from __future__ import annotations

import unittest
from unittest import mock

from core.note_model import Note
import web.io as web_io
from web_ui import Bridge


class ProjectWorkspacePreflightTests(unittest.TestCase):
    def make_bridge(self) -> Bridge:
        bridge = Bridge()
        bridge.notes = [Note(1.0, 2.0, 60.0).normalized()]
        bridge.duration = 10.0
        bridge._saved_checkpoint = bridge._document_checkpoint()
        bridge._redo_stack.append(bridge._snapshot())
        return bridge

    def test_invalid_workspace_metadata_preserves_current_document(self):
        invalid_settings = (
            {"workspace_duration": float("nan")},
            {"workspace_duration": float("inf")},
            {"workspace_midi_min": "invalid", "workspace_midi_max": 100},
            {"workspace_midi_min": 40, "workspace_midi_max": "invalid"},
        )
        for settings in invalid_settings:
            with self.subTest(settings=settings):
                bridge = self.make_bridge()
                before = bridge._document_checkpoint()
                previous_project_path = bridge.project_path
                with (
                    mock.patch.object(bridge, "_dialog", return_value="broken.adopyhz"),
                    mock.patch.object(
                        web_io,
                        "load_project",
                        return_value=(None, [Note(3.0, 4.0, 72.0)], settings),
                    ),
                    mock.patch.object(bridge, "_sync_notes_to_player") as sync,
                ):
                    with self.assertRaises((ValueError, OverflowError)):
                        bridge.load_project_dialog()
                self.assertEqual(bridge._document_checkpoint(), before)
                self.assertEqual(bridge.project_path, previous_project_path)
                self.assertEqual(len(bridge._undo_stack), 0)
                self.assertEqual(len(bridge._redo_stack), 1)
                self.assertFalse(bridge._dirty)
                sync.assert_not_called()

    def test_valid_workspace_metadata_restores_bounds_and_clears_history(self):
        bridge = self.make_bridge()
        settings = {
            "workspace_duration": 6.0,
            "workspace_midi_min": 110,
            "workspace_midi_max": 105,
        }
        with (
            mock.patch.object(bridge, "_dialog", return_value="valid.adopyhz"),
            mock.patch.object(
                web_io,
                "load_project",
                return_value=(None, [Note(3.0, 8.0, 72.0)], settings),
            ),
        ):
            result = bridge.load_project_dialog()

        self.assertEqual([(n.start, n.end) for n in bridge.notes], [(3.0, 8.0)])
        self.assertEqual(bridge.duration, 8.0)
        self.assertEqual((bridge.midi_min, bridge.midi_max), (110, 111))
        self.assertEqual(len(bridge._undo_stack), 0)
        self.assertEqual(len(bridge._redo_stack), 0)
        self.assertFalse(bridge._dirty)
        self.assertFalse(result["dirty"])


if __name__ == "__main__":
    unittest.main()
