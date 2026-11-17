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

    def test_invalid_workspace_does_not_reserve_source_request(self):
        bridge = self.make_bridge()
        generation_before = bridge._source_generation
        with (
            mock.patch.object(bridge, "_dialog", return_value="broken.adopyhz"),
            mock.patch.object(
                web_io, "load_project",
                return_value=(None, [Note(3.0, 4.0, 72.0)], {"workspace_duration": float("nan")}),
            ),
            mock.patch.object(bridge, "_reserve_source_request", wraps=bridge._reserve_source_request) as reserve,
        ):
            with self.assertRaises(ValueError):
                bridge.load_project_dialog()
        reserve.assert_not_called()
        self.assertEqual(bridge._source_generation, generation_before)

    def test_valid_workspace_reserves_source_request_once(self):
        bridge = self.make_bridge()
        generation_before = bridge._source_generation
        with (
            mock.patch.object(bridge, "_dialog", return_value="valid.adopyhz"),
            mock.patch.object(
                web_io, "load_project",
                return_value=(None, [Note(3.0, 4.0, 72.0)], {"workspace_duration": 10.0}),
            ),
            mock.patch.object(
                bridge, "_reserve_source_request",
                wraps=bridge._reserve_source_request,
            ) as reserve,
        ):
            bridge.load_project_dialog()
        reserve.assert_called_once_with()
        # The successful load reserves one request, then detaching the previous
        # audio source invalidates its analysis generation once more.
        self.assertEqual(bridge._source_generation, generation_before + 2)

    def test_non_finite_note_does_not_reserve_source_request(self):
        bridge = self.make_bridge()
        generation_before = bridge._source_generation
        with (
            mock.patch.object(bridge, "_dialog", return_value="broken.adopyhz"),
            mock.patch.object(
                web_io, "load_project",
                return_value=(None, [Note(float("nan"), 2.0, 60.0)], {}),
            ),
            mock.patch.object(
                bridge, "_reserve_source_request",
                wraps=bridge._reserve_source_request,
            ) as reserve,
        ):
            with self.assertRaises(ValueError):
                bridge.load_project_dialog()
        reserve.assert_not_called()
        self.assertEqual(bridge._source_generation, generation_before)

    def test_non_finite_project_notes_preserve_document_and_history(self):
        invalid_notes = (
            Note(float("nan"), 2.0, 60.0),
            Note(1.0, float("inf"), 60.0),
            Note(1.0, 2.0, float("nan")),
            Note(1.0, 2.0, 60.0, kind="curve", midi_end=float("inf")),
            Note(1.0, 2.0, 60.0, target_angle=float("nan")),
        )
        for invalid_note in invalid_notes:
            with self.subTest(note=invalid_note):
                bridge = self.make_bridge()
                before = bridge._document_checkpoint()
                previous_project_path = bridge.project_path
                with (
                    mock.patch.object(bridge, "_dialog", return_value="broken.adopyhz"),
                    mock.patch.object(
                        web_io, "load_project", return_value=(None, [invalid_note], {}),
                    ),
                    mock.patch.object(bridge, "_sync_notes_to_player") as sync,
                ):
                    with self.assertRaisesRegex(ValueError, "project note contains"):
                        bridge.load_project_dialog()
                self.assertEqual(bridge._document_checkpoint(), before)
                self.assertEqual(bridge.project_path, previous_project_path)
                self.assertEqual(len(bridge._undo_stack), 0)
                self.assertEqual(len(bridge._redo_stack), 1)
                self.assertFalse(bridge._dirty)
                sync.assert_not_called()

    def test_audio_preparation_failure_keeps_document_and_invalidates_older_request(self):
        bridge = self.make_bridge()
        checkpoint_before = bridge._document_checkpoint()
        project_path_before = bridge.project_path
        audio_path_before = bridge.audio_path
        status_before = bridge._status
        source_generation_before = bridge._source_generation
        analysis_generation_before = bridge._analysis_generation
        with (
            mock.patch.object(bridge, "_dialog", return_value="with-audio.adopyhz"),
            mock.patch.object(
                web_io,
                "load_project",
                return_value=("audio.wav", [Note(3.0, 4.0, 72.0)], {}),
            ),
            mock.patch.object(web_io.Path, "exists", return_value=True),
            mock.patch.object(
                bridge,
                "_prepare_requested_audio_path",
                side_effect=ValueError("audio preparation failed"),
            ) as prepare,
            mock.patch.object(
                bridge, "_reserve_source_request", wraps=bridge._reserve_source_request,
            ) as reserve,
            mock.patch.object(bridge, "_sync_notes_to_player") as sync,
        ):
            with self.assertRaisesRegex(ValueError, "audio preparation failed"):
                bridge.load_project_dialog()

        prepare.assert_called_once()
        reserve.assert_called_once_with()
        sync.assert_not_called()
        self.assertEqual(bridge._document_checkpoint(), checkpoint_before)
        self.assertEqual(bridge.project_path, project_path_before)
        self.assertEqual(bridge.audio_path, audio_path_before)
        self.assertEqual(bridge._status, status_before)
        self.assertEqual(len(bridge._undo_stack), 0)
        self.assertEqual(len(bridge._redo_stack), 1)
        self.assertFalse(bridge._dirty)
        self.assertFalse(bridge._busy)
        # Source reservations use last-started-request-wins semantics even when
        # preparation fails. An older request must not later replace the document.
        self.assertEqual(bridge._source_generation, source_generation_before + 1)
        self.assertEqual(bridge._analysis_generation, analysis_generation_before + 1)
        self.assertFalse(
            bridge._commit_prepared_audio(
                "older.wav", None, None, source_generation=source_generation_before,
            )
        )
        self.assertEqual(bridge._document_checkpoint(), checkpoint_before)

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
