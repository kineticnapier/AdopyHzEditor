from __future__ import annotations

import threading
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
        self.evaluate_threads: list[int] = []
        self.script_event = threading.Event()
        self.destroyed = False

    def evaluate_js(self, script: str) -> None:
        self.evaluate_threads.append(threading.get_ident())
        self.scripts.append(script)
        self.script_event.set()

    def destroy(self) -> None:
        self.destroyed = True


class _BlockingCloseWindow(_CloseWindow):
    def __init__(self) -> None:
        super().__init__()
        self.release_evaluate = threading.Event()

    def evaluate_js(self, script: str) -> None:
        super().evaluate_js(script)
        self.release_evaluate.wait(2.0)


class _FailingDestroyWindow(_CloseWindow):
    def destroy(self) -> None:
        raise RuntimeError("native destroy failed")


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

    def test_existing_project_saves_in_place_without_dialog(self):
        bridge = Bridge()
        project_path = str(Path("existing.adopyhz").resolve())
        bridge.project_path = project_path
        bridge._dirty = True

        with (
            mock.patch.object(bridge, "_dialog") as dialog,
            mock.patch.object(web_io, "save_project") as save_project,
        ):
            result = bridge.save_project_dialog()

        dialog.assert_not_called()
        save_project.assert_called_once()
        self.assertEqual(save_project.call_args.args[0], project_path)
        self.assertFalse(result["dirty"])

    def test_window_close_is_cancelled_until_frontend_resolves_dirty_state(self):
        bridge = Bridge()
        window = _CloseWindow()
        bridge.attach_window(window)
        bridge._dirty = True

        self.assertFalse(bridge.on_window_closing())
        self.assertTrue(window.script_event.wait(1.0))
        self.assertEqual(len(window.scripts), 1)
        self.assertIn("adopyhz-close-requested", window.scripts[0])
        self.assertNotEqual(window.evaluate_threads[0], threading.get_ident())
        self.assertFalse(window.destroyed)

        self.assertTrue(bridge.close_window()["ok"])
        self.assertTrue(window.destroyed)
        self.assertTrue(bridge.on_window_closing())

    def test_close_callback_does_not_wait_for_evaluate_js(self):
        bridge = Bridge()
        window = _BlockingCloseWindow()
        bridge.attach_window(window)
        bridge._dirty = True
        callback_done = threading.Event()
        callback_results: list[bool] = []

        def invoke_close_callback() -> None:
            callback_results.append(bridge.on_window_closing())
            callback_done.set()

        callback_thread = threading.Thread(target=invoke_close_callback)
        callback_thread.start()
        try:
            self.assertTrue(window.script_event.wait(1.0))
            self.assertTrue(callback_done.wait(0.5))
            self.assertEqual(callback_results, [False])
        finally:
            window.release_evaluate.set()
            callback_thread.join(1.0)

    def test_modal_cancel_keeps_dirty_window_open_and_allows_retry(self):
        bridge = Bridge()
        window = _CloseWindow()
        bridge.attach_window(window)
        bridge._dirty = True

        self.assertFalse(bridge.on_window_closing())
        self.assertTrue(window.script_event.wait(1.0))
        self.assertTrue(bridge._window_close_pending)
        self.assertTrue(bridge.cancel_window_close()["ok"])

        self.assertTrue(bridge._dirty)
        self.assertFalse(window.destroyed)
        self.assertFalse(bridge._allow_window_close)
        self.assertFalse(bridge._window_close_pending)
        window.script_event.clear()
        self.assertFalse(bridge.on_window_closing())
        self.assertTrue(window.script_event.wait(1.0))
        self.assertEqual(len(window.scripts), 2)

    def test_save_dialog_cancel_keeps_dirty_window_open(self):
        bridge = Bridge()
        window = _CloseWindow()
        bridge.attach_window(window)
        bridge._dirty = True

        self.assertFalse(bridge.on_window_closing())
        self.assertTrue(window.script_event.wait(1.0))
        with mock.patch.object(bridge, "_dialog", return_value=None):
            result = bridge.save_project_dialog()
        bridge.cancel_window_close()

        self.assertTrue(result["dirty"])
        self.assertTrue(bridge._dirty)
        self.assertFalse(window.destroyed)
        self.assertFalse(bridge._allow_window_close)
        self.assertFalse(bridge._window_close_pending)

    def test_save_success_then_close(self):
        bridge = Bridge()
        window = _CloseWindow()
        bridge.attach_window(window)
        bridge._dirty = True

        self.assertFalse(bridge.on_window_closing())
        self.assertTrue(window.script_event.wait(1.0))
        with (
            mock.patch.object(bridge, "_dialog", return_value="saved.adopyhz"),
            mock.patch.object(web_io, "save_project"),
        ):
            result = bridge.save_project_dialog()
        bridge.close_window()

        self.assertFalse(result["dirty"])
        self.assertTrue(window.destroyed)
        self.assertTrue(bridge._allow_window_close)

    def test_discard_then_close(self):
        bridge = Bridge()
        window = _CloseWindow()
        bridge.attach_window(window)
        bridge._dirty = True

        self.assertFalse(bridge.on_window_closing())
        self.assertTrue(window.script_event.wait(1.0))
        bridge.close_window()

        self.assertTrue(bridge._dirty)
        self.assertTrue(window.destroyed)
        self.assertTrue(bridge.on_window_closing())

    def test_clean_window_closes_without_frontend_round_trip(self):
        bridge = Bridge()
        window = _CloseWindow()
        bridge.attach_window(window)

        self.assertTrue(bridge.on_window_closing())
        self.assertFalse(window.script_event.wait(0.05))
        self.assertFalse(bridge._window_close_pending)

    def test_destroy_failure_does_not_leave_close_allowed(self):
        bridge = Bridge()
        bridge.attach_window(_FailingDestroyWindow())
        bridge._dirty = True

        with self.assertRaisesRegex(RuntimeError, "native destroy failed"):
            bridge.close_window()

        self.assertFalse(bridge._allow_window_close)

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
