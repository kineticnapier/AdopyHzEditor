from __future__ import annotations

import json
import tempfile
from pathlib import Path
import unittest
from unittest import mock

from core.note_model import Note
from core.project_io import (
    InvalidProjectVersionError,
    PROJECT_VERSION,
    UnsupportedProjectVersionError,
    load_project,
)
from web_ui import Bridge


class ProjectVersionCompatibilityTests(unittest.TestCase):
    def _write_project(self, directory: str, *, version=...) -> Path:
        data = {
            "audio_path": None,
            "settings": {"grid_bpm": 222.0},
            "notes": [Note(0.25, 0.75, 69.0).to_dict()],
        }
        if version is not ...:
            data["version"] = version
        path = Path(directory) / "version-test.adopyhz"
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def test_legacy_project_without_version_loads(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            _audio, notes, settings = load_project(self._write_project(temp_dir))
        self.assertEqual(len(notes), 1)
        self.assertEqual(settings["grid_bpm"], 222.0)

    def test_older_supported_version_loads(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            _audio, notes, _settings = load_project(self._write_project(temp_dir, version=1))
        self.assertEqual(len(notes), 1)

    def test_current_version_loads(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            _audio, notes, _settings = load_project(
                self._write_project(temp_dir, version=PROJECT_VERSION)
            )
        self.assertEqual(len(notes), 1)

    def test_future_version_has_clear_dedicated_error(self):
        future = PROJECT_VERSION + 1
        with tempfile.TemporaryDirectory() as temp_dir:
            path = self._write_project(temp_dir, version=future)
            with self.assertRaises(UnsupportedProjectVersionError) as caught:
                load_project(path)
        self.assertEqual(caught.exception.version, future)
        self.assertIn("アプリを更新してください", str(caught.exception))

    def test_invalid_versions_are_rejected(self):
        for value in (None, True, "3", 3.5, 0, -1):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as temp_dir:
                with self.assertRaises(InvalidProjectVersionError):
                    load_project(self._write_project(temp_dir, version=value))

    def test_future_version_does_not_change_existing_web_editor_state(self):
        bridge = Bridge()
        bridge.project_path = str(Path("current.adopyhz").resolve())
        bridge.audio_path = str(Path("current.ogg").resolve())
        bridge.notes = [Note(1.0, 2.0, 72.0).normalized()]
        bridge.settings["bpm"] = 321.0
        bridge._dirty = True
        before = bridge.get_state()

        with tempfile.TemporaryDirectory() as temp_dir:
            path = self._write_project(temp_dir, version=PROJECT_VERSION + 1)
            with (
                mock.patch.object(bridge, "_dialog", return_value=str(path)),
                self.assertRaises(UnsupportedProjectVersionError),
            ):
                bridge.load_project_dialog()

        self.assertEqual(bridge.get_state(), before)


if __name__ == "__main__":
    unittest.main()
