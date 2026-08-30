from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import numpy as np

import web.backend as web_backend
import web.io as web_io
import web.tools as web_tools
from core.note_model import Note
from web_ui import Bridge


class _CloseWindow:
    def __init__(self) -> None:
        self.scripts: list[str] = []
        self.destroyed = False

    def evaluate_js(self, script: str) -> None:
        self.scripts.append(script)

    def destroy(self) -> None:
        self.destroyed = True


class UnsavedDataProtectionTests(unittest.TestCase):
    def test_open_audio_keeps_existing_dirty_state(self):
        bridge = Bridge()
        bridge.notes = [Note(0.0, 1.0, 69.0).normalized()]
        bridge._dirty = True
        decoded = SimpleNamespace(
            samples=np.zeros((32, 2), dtype=np.float32),
            sample_rate=44100,
            duration=32 / 44100,
        )

        with (
            mock.patch.object(bridge, "_file_dialog", return_value=["replacement.wav"]),
            mock.patch.object(web_backend, "decode_audio_file", return_value=decoded),
            mock.patch.object(bridge, "_analyze_current_audio"),
        ):
            result = bridge.open_audio()

        self.assertTrue(result["dirty"])
        self.assertEqual(len(result["notes"]), 1)

    def test_opening_new_audio_marks_clean_project_dirty(self):
        bridge = Bridge()
        bridge.audio_path = "old.wav"
        bridge._dirty = False
        decoded = SimpleNamespace(
            samples=np.zeros((32, 2), dtype=np.float32),
            sample_rate=44100,
            duration=32 / 44100,
        )

        with (
            mock.patch.object(bridge, "_file_dialog", return_value=["replacement.wav"]),
            mock.patch.object(web_backend, "decode_audio_file", return_value=decoded),
            mock.patch.object(bridge, "_analyze_current_audio"),
        ):
            result = bridge.open_audio()

        self.assertTrue(result["dirty"])

    def test_notes_only_load_is_an_unsaved_derived_workspace(self):
        bridge = Bridge()
        note = Note(0.25, 0.75, 69.0).normalized()
        source = str(Path("source.adopyhz").resolve())

        with (
            mock.patch.object(bridge, "_dialog", return_value=source),
            mock.patch.object(web_tools, "load_project", return_value=("song.ogg", [note], {})),
        ):
            result = bridge.load_project_notes_only_dialog()

        self.assertIsNone(result["projectPath"])
        self.assertIsNone(result["audio"]["path"])
        self.assertTrue(result["dirty"])

    def test_cancelled_destructive_file_dialog_preserves_state(self):
        bridge = Bridge()
        bridge.project_path = str(Path("current.adopyhz").resolve())
        bridge.audio_path = str(Path("current.wav").resolve())
        bridge.notes = [Note(1.0, 2.0, 72.0).normalized()]
        bridge._dirty = True
        before = bridge.get_state()

        with mock.patch.object(bridge, "_dialog", return_value=None):
            bridge.load_project_dialog()
            bridge.load_project_notes_only_dialog()
        with mock.patch.object(bridge, "_file_dialog", return_value=[]):
            bridge.open_audio()

        after = bridge.get_state()
        self.assertEqual(after["projectPath"], before["projectPath"])
        self.assertEqual(after["audio"], before["audio"])
        self.assertEqual(after["notes"], before["notes"])
        self.assertTrue(after["dirty"])

    def test_dirty_clears_only_after_successful_save(self):
        bridge = Bridge()
        bridge._dirty = True

        with mock.patch.object(bridge, "_dialog", return_value=None):
            self.assertTrue(bridge.save_project_dialog()["dirty"])

        with (
            mock.patch.object(bridge, "_dialog", return_value="saved.adopyhz"),
            mock.patch.object(web_io, "save_project") as save_project,
        ):
            result = bridge.save_project_dialog()

        save_project.assert_called_once()
        self.assertFalse(result["dirty"])

    def test_window_close_is_cancelled_until_frontend_resolves_dirty_state(self):
        bridge = Bridge()
        window = _CloseWindow()
        bridge.attach_window(window)
        bridge._dirty = True

        self.assertFalse(bridge.on_window_closing())
        self.assertEqual(len(window.scripts), 1)
        self.assertIn("adopyhz-close-requested", window.scripts[0])
        self.assertFalse(window.destroyed)

        self.assertTrue(bridge.close_window()["ok"])
        self.assertTrue(window.destroyed)
        self.assertTrue(bridge.on_window_closing())

    def test_relink_behavior_still_marks_project_dirty(self):
        bridge = Bridge()
        bridge.project_path = str(Path("project.adopyhz").resolve())
        bridge._dirty = False

        with (
            mock.patch.object(bridge, "_dialog", return_value="replacement.ogg"),
            mock.patch.object(bridge, "_load_audio_path"),
        ):
            result = bridge.relink_project_audio_dialog()

        self.assertTrue(result["dirty"])


if __name__ == "__main__":
    unittest.main()
