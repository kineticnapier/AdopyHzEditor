from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import core.project_io as project_io
from core.note_model import Note


class AtomicProjectSaveTests(unittest.TestCase):
    def _temp_files(self, directory: Path, target_name: str) -> list[Path]:
        return list(directory.glob(f".{target_name}.*.tmp"))

    def test_normal_save_keeps_existing_project_format(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            project = directory / "project.adopyhz"
            audio = directory / "song.ogg"
            note = Note(0.25, 0.75, 69.0).normalized()

            project_io.save_project(
                project,
                audio_path=str(audio),
                notes=[note],
                settings={"grid_bpm": 175.0},
            )

            data = json.loads(project.read_text(encoding="utf-8"))
            self.assertEqual(data["version"], project_io.PROJECT_VERSION)
            self.assertEqual(data["audio_path"], str(audio))
            self.assertEqual(data["audio_path_relative"], "song.ogg")
            self.assertEqual(data["audio_filename"], "song.ogg")
            self.assertEqual(data["settings"], {"grid_bpm": 175.0})
            self.assertEqual(len(data["notes"]), 1)
            self.assertEqual(self._temp_files(directory, project.name), [])

    def test_existing_project_is_replaced(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            project = directory / "project.adopyhz"
            project.write_text("old project", encoding="utf-8")

            project_io.save_project(
                project,
                audio_path=None,
                notes=[],
                settings={"grid_bpm": 200.0},
            )

            self.assertNotEqual(project.read_text(encoding="utf-8"), "old project")
            self.assertEqual(json.loads(project.read_text(encoding="utf-8"))["settings"]["grid_bpm"], 200.0)

    def test_write_failure_preserves_existing_project_and_cleans_temp(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            project = directory / "project.adopyhz"
            project.write_text("known-good", encoding="utf-8")

            with mock.patch.object(project_io.os, "fsync", side_effect=OSError("disk full")):
                with self.assertRaises(OSError):
                    project_io.save_project(project, audio_path=None, notes=[], settings={})

            self.assertEqual(project.read_text(encoding="utf-8"), "known-good")
            self.assertEqual(self._temp_files(directory, project.name), [])

    def test_replace_failure_preserves_existing_project_and_cleans_temp(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            project = directory / "project.adopyhz"
            project.write_text("known-good", encoding="utf-8")

            with mock.patch.object(project_io.os, "replace", side_effect=OSError("locked")):
                with self.assertRaises(OSError):
                    project_io.save_project(project, audio_path=None, notes=[], settings={})

            self.assertEqual(project.read_text(encoding="utf-8"), "known-good")
            self.assertEqual(self._temp_files(directory, project.name), [])


if __name__ == "__main__":
    unittest.main()
