from __future__ import annotations

import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest import mock

import web.backend as web_backend
import web.io as web_io
from core.note_model import Note
from core.project_io import save_project
from web.io import DEFAULT_EDITOR_SETTINGS
from web_ui import Bridge


class BackendConsistencyRound2Tests(unittest.TestCase):
    def test_open_audio_analysis_failure_preserves_previous_document_state(self):
        bridge = Bridge()
        old_audio = str(Path("old.wav").resolve())
        bridge.audio_path = old_audio
        bridge.project_audio_reference = old_audio
        bridge.project_path = str(Path("old.adopyhz").resolve())
        bridge.notes = [Note(1.0, 2.0, 60.0).normalized()]
        bridge.duration = 12.0
        bridge._dirty = True
        bridge._status = "Ready"
        before = bridge.get_state()
        decoded = SimpleNamespace(samples=None, sample_rate=44100, duration=2.0)

        with (
            mock.patch.object(bridge, "_file_dialog", return_value=["replacement.wav"]),
            mock.patch.object(web_backend, "decode_audio_file", return_value=decoded),
            mock.patch.object(web_backend, "analyze_cqt", side_effect=RuntimeError("analysis failed")),
        ):
            with self.assertRaisesRegex(RuntimeError, "analysis failed"):
                bridge.open_audio()

        after = bridge.get_state()
        self.assertEqual(after["audio"], before["audio"])
        self.assertEqual(after["notes"], before["notes"])
        self.assertEqual(after["projectPath"], before["projectPath"])
        self.assertEqual(after["dirty"], before["dirty"])
        self.assertEqual(bridge.duration, 12.0)
        self.assertEqual(bridge.project_audio_reference, old_audio)
        self.assertEqual(bridge._status, "Ready")

    def test_missing_project_settings_restore_canonical_defaults_not_previous_document(self):
        bridge = Bridge()
        bridge.settings["speed"] = 2.0
        bridge.settings["snapEnabled"] = True
        bridge.settings["volume"] = 12

        bridge._apply_project_settings({"grid_bpm": 240.0})

        self.assertEqual(bridge.settings["bpm"], 240.0)
        self.assertEqual(bridge.settings["speed"], DEFAULT_EDITOR_SETTINGS["speed"])
        self.assertEqual(bridge.settings["snapEnabled"], DEFAULT_EDITOR_SETTINGS["snapEnabled"])
        self.assertEqual(bridge.settings["volume"], DEFAULT_EDITOR_SETTINGS["volume"])

    def test_midi_import_undo_redo_restores_document_duration(self):
        bridge = Bridge()
        bridge.duration = 60.0
        imported = [Note(80.0, 90.0, 72.0).normalized()]

        with (
            mock.patch.object(bridge, "_dialog", return_value="long.mid"),
            mock.patch.object(web_io, "import_midi", return_value=SimpleNamespace(notes=imported)),
        ):
            bridge.import_midi_dialog()

        self.assertEqual(bridge.duration, 90.0)
        self.assertEqual(len(bridge.notes), 1)

        undone = bridge.undo()
        self.assertTrue(undone["changed"])
        self.assertEqual(bridge.duration, 60.0)
        self.assertEqual(bridge.notes, [])

        redone = bridge.redo()
        self.assertTrue(redone["changed"])
        self.assertEqual(bridge.duration, 90.0)
        self.assertEqual(len(bridge.notes), 1)

        bridge.undo()
        self.assertEqual(bridge.duration, 60.0)

    def test_missing_audio_reference_survives_load_edit_and_save(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project.adopyhz"
            missing_audio = root / "missing" / "song.ogg"
            save_project(
                project,
                audio_path=str(missing_audio),
                notes=[Note(0.0, 1.0, 60.0).normalized()],
                settings={},
            )

            bridge = Bridge()
            with mock.patch.object(bridge, "_dialog", return_value=str(project)):
                result = bridge.load_project_dialog()

            self.assertIsNone(result["audio"]["path"])
            self.assertEqual(bridge.project_audio_reference, str(missing_audio))
            bridge.notes.append(Note(2.0, 3.0, 64.0).normalized())
            bridge._dirty = True
            bridge._save_project_path(str(project))

            saved = json.loads(project.read_text(encoding="utf-8"))
            self.assertEqual(saved["audio_path"], str(missing_audio))
            self.assertEqual(saved["audio_filename"], "song.ogg")
            self.assertTrue(saved["audio_path_relative"])

    def test_blank_workspace_bounds_round_trip_through_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "workspace.adopyhz"
            bridge = Bridge()
            bridge.apply_blank_workspace(
                {"duration": 180.0, "midiMin": 36, "midiMax": 84}
            )
            bridge.notes = [Note(10.0, 11.0, 60.0).normalized()]
            bridge._save_project_path(str(project))

            restored = Bridge()
            with mock.patch.object(restored, "_dialog", return_value=str(project)):
                restored.load_project_dialog()

            defaults = restored.get_blank_workspace_defaults()
            self.assertEqual(defaults["duration"], 180.0)
            self.assertEqual(defaults["midiMin"], 36)
            self.assertEqual(defaults["midiMax"], 84)
            self.assertEqual(len(restored.notes), 1)


if __name__ == "__main__":
    unittest.main()
