from __future__ import annotations

import unittest
from unittest import mock

from core.note_model import Note
from web_ui import Bridge


class AdoFAISongSourceTests(unittest.TestCase):
    def test_defaults_use_current_project_audio(self):
        bridge = Bridge()
        bridge.audio_path = "/music/analysis.wav"
        bridge.notes = [Note(0.5, 1.0, 69.0).normalized()]

        defaults = bridge.get_adofai_export_defaults()

        self.assertTrue(defaults["useProjectSong"])
        self.assertEqual(defaults["songSourcePath"], bridge.audio_path)

    def test_custom_song_source_does_not_replace_analysis_audio(self):
        bridge = Bridge()
        bridge.audio_path = "/music/analysis.wav"
        bridge.notes = [Note(0.5, 1.0, 69.0).normalized()]

        _notes, build_opts, workflow = bridge._prepare_adofai_export(
            {
                "method": "rabbit_zip",
                "useProjectSong": True,
                "copyProjectSong": True,
                "songSourcePath": "/adofai/playback.ogg",
                "songOffsetAuto": False,
                "songOffsetMs": 123.0,
            },
            None,
        )

        self.assertEqual(bridge.audio_path, "/music/analysis.wav")
        self.assertEqual(build_opts["song_filename"], "playback.ogg")
        self.assertEqual(build_opts["song_offset_ms"], 123.0)
        self.assertEqual(workflow["songSourcePath"], "/adofai/playback.ogg")
        self.assertTrue(workflow["copySong"])

    def test_custom_song_source_works_without_loaded_project_audio(self):
        bridge = Bridge()
        bridge.notes = [Note(0.25, 0.75, 69.0).normalized()]

        _notes, build_opts, workflow = bridge._prepare_adofai_export(
            {
                "method": "rabbit_zip",
                "useProjectSong": True,
                "copyProjectSong": False,
                "songSourcePath": "/tmp/playback.flac",
                "songOffsetAuto": True,
            },
            None,
        )

        self.assertEqual(build_opts["song_filename"], "playback.flac")
        self.assertAlmostEqual(build_opts["song_offset_ms"], 250.0)
        self.assertEqual(workflow["songSourcePath"], "/tmp/playback.flac")
        self.assertFalse(workflow["copySong"])

    def test_song_source_picker_returns_selected_path(self):
        bridge = Bridge()
        with mock.patch.object(bridge, "_dialog", return_value="relative/song.ogg"):
            result = bridge.choose_adofai_song_source()

        self.assertTrue(result["ok"])
        self.assertEqual(result["name"], "song.ogg")
        self.assertTrue(result["path"].endswith("song.ogg"))


if __name__ == "__main__":
    unittest.main()
