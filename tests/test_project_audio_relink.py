from __future__ import annotations

from pathlib import Path
import unittest
from unittest import mock

import web.io as web_io
from core.note_model import Note
from web_ui import Bridge


class ProjectAudioRelinkTests(unittest.TestCase):
    def test_relink_requires_loaded_project(self):
        bridge = Bridge()
        with mock.patch.object(bridge, "_dialog") as dialog:
            result = bridge.relink_project_audio_dialog()

        dialog.assert_not_called()
        self.assertIn("先にプロジェクト", result["status"])
        self.assertFalse(result["dirty"])

    def test_relink_replaces_project_audio_and_marks_dirty(self):
        bridge = Bridge()
        bridge.project_path = str(Path("project.adopyhz").resolve())
        bridge.notes = [Note(0.25, 0.75, 69.0).normalized()]
        expected = str(Path("replacement.ogg").resolve())

        def fake_load(path, *, analyze=True):
            self.assertTrue(analyze)
            bridge.audio_path = str(path)
            bridge.duration = 2.0

        with (
            mock.patch.object(bridge, "_dialog", return_value="replacement.ogg"),
            mock.patch.object(bridge, "_load_audio_path", side_effect=fake_load) as load_audio,
        ):
            result = bridge.relink_project_audio_dialog()

        load_audio.assert_called_once_with(expected, analyze=True)
        self.assertEqual(result["audio"]["path"], expected)
        self.assertEqual(result["audio"]["name"], "replacement.ogg")
        self.assertTrue(result["dirty"])
        self.assertIn("再指定しました", result["status"])

    def test_missing_project_audio_explains_how_to_relink(self):
        bridge = Bridge()
        note = Note(0.25, 0.75, 69.0).normalized()
        missing = str(Path("definitely-missing-project-audio.ogg").resolve())

        with (
            mock.patch.object(bridge, "_dialog", return_value="project.adopyhz"),
            mock.patch.object(web_io, "load_project", return_value=(missing, [note], {})),
        ):
            result = bridge.load_project_dialog()

        self.assertIsNone(result["audio"]["path"])
        self.assertIn("音源が見つかりません", result["status"])
        self.assertIn("プロジェクト音源を再指定", result["status"])

    def test_project_save_uses_relinked_audio_path(self):
        bridge = Bridge()
        bridge.project_path = str(Path("old-project.adopyhz").resolve())
        bridge.audio_path = str(Path("replacement.flac").resolve())
        bridge.notes = [Note(0.0, 0.5, 69.0).normalized()]

        with (
            mock.patch.object(bridge, "_dialog", return_value="saved-project.adopyhz"),
            mock.patch.object(web_io, "save_project") as save_project,
        ):
            bridge.save_project_dialog()

        self.assertEqual(save_project.call_args.kwargs["audio_path"], bridge.audio_path)


if __name__ == "__main__":
    unittest.main()
