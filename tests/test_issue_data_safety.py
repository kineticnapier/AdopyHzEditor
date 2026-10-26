from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

import web.adofai as web_adofai
import web.io as web_io
import core.atomic_io as atomic_io
from core.note_model import Note
from core.project_loading import resolve_project_audio_plan
from tools import quick_hz
from web_ui import Bridge


class IssueDataSafetyTests(unittest.TestCase):
    def test_desktop_project_cancel_does_not_apply_any_new_state(self):
        locate = mock.Mock()
        plan = resolve_project_audio_plan(
            "song.wav",
            notes_only=False,
            choose_mode=lambda _audio: "cancel",
            locate_audio=locate,
        )
        self.assertFalse(plan.accepted)
        locate.assert_not_called()

    def test_blank_workspace_detaches_original_project_path(self):
        bridge = Bridge()
        bridge.project_path = str(Path("original.adopyhz").resolve())

        result = bridge.apply_blank_workspace({"duration": 30, "midiMin": 12, "midiMax": 108})

        self.assertIsNone(result["projectPath"])
        self.assertTrue(result["dirty"])

    def test_project_audio_failure_preserves_complete_previous_state(self):
        bridge = Bridge()
        old_note = Note(1.0, 2.0, 60.0).normalized()
        bridge.notes = [old_note]
        bridge.project_path = str(Path("old.adopyhz").resolve())
        bridge.audio_path = str(Path("old.wav").resolve())
        bridge.settings["bpm"] = 123.0
        bridge._dirty = True
        bridge._undo_stack = [[old_note.to_dict()]]
        before = bridge.get_state()
        new_note = Note(3.0, 4.0, 72.0).normalized()

        with (
            mock.patch.object(bridge, "_dialog", return_value="new.adopyhz"),
            mock.patch.object(web_io, "load_project", return_value=("broken.wav", [new_note], {"grid_bpm": 200})),
            mock.patch.object(web_io.Path, "exists", return_value=True),
            mock.patch.object(bridge, "_prepare_audio_path", side_effect=RuntimeError("decode failed")),
        ):
            with self.assertRaisesRegex(RuntimeError, "decode failed"):
                bridge.load_project_dialog()

        after = bridge.get_state()
        self.assertEqual(after["notes"], before["notes"])
        self.assertEqual(after["projectPath"], before["projectPath"])
        self.assertEqual(after["audio"], before["audio"])
        self.assertEqual(after["settings"]["bpm"], before["settings"]["bpm"])
        self.assertEqual(after["dirty"], before["dirty"])
        self.assertEqual(bridge._undo_stack, [[old_note.to_dict()]])

    def test_corrupt_preset_file_is_not_silently_replaced(self):
        bridge = Bridge()
        bridge.notes = [Note(0.0, 1.0, 60.0).normalized()]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "note-presets.json"
            path.write_text("{broken", encoding="utf-8")
            with mock.patch.object(bridge, "_note_preset_path", return_value=path):
                with self.assertRaises(ValueError):
                    bridge.save_note_preset("new", 0)
            self.assertEqual(path.read_text(encoding="utf-8"), "{broken")

    def test_quick_hz_replace_failure_preserves_existing_chart(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "level.adofai"
            path.write_bytes(b"known-good")
            with mock.patch.object(atomic_io.os, "replace", side_effect=OSError("locked")):
                with self.assertRaises(quick_hz.HzToolError):
                    quick_hz.SaveChartAs({"angleData": [180]}, path, overwrite=True)
            self.assertEqual(path.read_bytes(), b"known-good")
            self.assertEqual(list(path.parent.glob(".level.adofai.*.tmp")), [])

    def test_audio_copy_failure_preserves_existing_adofai_chart(self):
        bridge = Bridge()
        bridge.notes = [Note(0.0, 0.5, 69.0).normalized()]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_dir = root / "source"
            output_dir = root / "output"
            source_dir.mkdir()
            output_dir.mkdir()
            source = source_dir / "source.ogg"
            source.write_bytes(b"song")
            chart = output_dir / "level.adofai"
            chart.write_bytes(b"known-good-chart")
            options = bridge.get_adofai_export_defaults()
            options.update(useProjectSong=True, copyProjectSong=True, songSourcePath=str(source))
            with (
                mock.patch.object(bridge, "_dialog", return_value=str(chart)),
                mock.patch.object(web_adofai, "build_adofai_level", return_value=({"angleData": [0], "actions": []}, {"tiles_total": 0})),
                mock.patch.object(web_adofai, "_copy_song_atomic", side_effect=OSError("copy failed")),
            ):
                result = bridge.export_adofai_advanced(options)
            self.assertFalse(result["ok"])
            self.assertEqual(chart.read_bytes(), b"known-good-chart")


if __name__ == "__main__":
    unittest.main()
