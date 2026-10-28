from __future__ import annotations

import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest import mock

import numpy as np

import web.backend as web_backend
import web.io as web_io
from core.audio_analysis import Spectrogram
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


    def _mock_cqt_spectrogram(self, duration=10.0):
        return Spectrogram(
            audio_path="mock.wav",
            db=np.zeros((2, 2), dtype=np.float32),
            duration=duration,
            midi_min=60,
            midi_max=61,
            frame_times=np.array([0.0, duration]),
            sr=44100,
        )

    def test_reanalysis_cqt_preserves_tail_notes_and_seek_range(self):
        bridge = Bridge()
        bridge.audio_path = "mock.wav"
        bridge.notes = [Note(12.0, 13.0, 60.0).normalized()]
        bridge.duration = 13.0
        bridge.player.set_virtual_duration(13.0)

        with mock.patch.object(
            web_backend, "analyze_cqt",
            return_value=self._mock_cqt_spectrogram(),
        ):
            result = bridge._analyze_current_audio(explicit=True)

        self.assertEqual(result, "cqt")
        self.assertEqual(bridge.duration, 13.0)
        self.assertEqual(len(bridge.notes), 1)
        self.assertAlmostEqual(bridge.seek_to(12.5)["time"], 12.5, places=3)

    def test_reanalysis_direct_preserves_tail_notes_and_seek_range(self):
        bridge = Bridge()
        bridge.audio_path = "mock.ogg"
        bridge.settings["analysisSource"] = "vorbis_direct"
        bridge.notes = [Note(12.0, 13.0, 60.0).normalized()]
        bridge.duration = 13.0
        bridge.player.set_virtual_duration(13.0)
        store = SimpleNamespace(
            duration=10.0,
            stats=SimpleNamespace(to_dict=lambda: {
                "storedBins": 1, "blocksProcessed": 1, "analysisSeconds": 0.0,
            }),
        )
        tracks = SimpleNamespace(
            stats=SimpleNamespace(to_dict=lambda: {"totalTrackCount": 0}),
        )

        with (
            mock.patch.object(
                web_backend, "select_analysis_backend",
                return_value=SimpleNamespace(selected="vorbis_direct"),
            ),
            mock.patch.object(
                web_backend, "analyze_vorbis_spectrum_store", return_value=store,
            ),
            mock.patch.object(
                web_backend, "build_frequency_track_store", return_value=tracks,
            ),
        ):
            result = bridge._analyze_current_audio(explicit=True)

        self.assertEqual(result, "vorbis_direct")
        self.assertEqual(bridge.duration, 13.0)
        self.assertAlmostEqual(bridge.seek_to(12.5)["time"], 12.5, places=3)

    def test_reanalysis_without_tail_notes_uses_audio_duration(self):
        bridge = Bridge()
        bridge.audio_path = "mock.wav"
        bridge.notes = [Note(1.0, 2.0, 60.0).normalized()]
        bridge.duration = 13.0
        bridge.player.set_virtual_duration(13.0)

        with mock.patch.object(
            web_backend, "analyze_cqt",
            return_value=self._mock_cqt_spectrogram(),
        ):
            bridge._analyze_current_audio(explicit=True)

        self.assertEqual(bridge.duration, 10.0)
        self.assertEqual(len(bridge.notes), 1)
        self.assertAlmostEqual(bridge.seek_to(12.5)["time"], 10.0, places=3)

if __name__ == "__main__":
    unittest.main()
