from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from core.note_model import Note
import web.adofai as web_adofai
from web_ui import Bridge


def _fake_level(_notes, **options):
    return (
        {"settings": {"songFilename": options.get("song_filename")}, "angleData": [0.0], "actions": []},
        {"tiles_total": 0},
    )


class AdoFAIAudioCopySafetyTests(unittest.TestCase):
    def _export(self, source: Path, chart: Path, action: str = "cancel"):
        bridge = Bridge()
        bridge.audio_path = str(Path("analysis.wav").resolve())
        bridge.notes = [Note(0.0, 0.5, 69.0).normalized()]
        defaults = bridge.get_adofai_export_defaults()
        defaults.update(
            useProjectSong=True,
            copyProjectSong=True,
            songSourcePath=str(source),
            songConflictAction=action,
        )
        with (
            mock.patch.object(bridge, "_dialog", return_value=str(chart)),
            mock.patch.object(web_adofai, "build_adofai_level", side_effect=_fake_level),
        ):
            result = bridge.export_adofai_advanced(defaults)
        return bridge, result

    def test_missing_target_is_copied_and_song_filename_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_dir = root / "source"
            output_dir = root / "output"
            source_dir.mkdir()
            output_dir.mkdir()
            source = source_dir / "song.ogg"
            source.write_bytes(b"song data")
            chart = output_dir / "level.adofai"

            bridge, result = self._export(source, chart)

            target = output_dir / "song.ogg"
            self.assertTrue(result["ok"])
            self.assertEqual(target.read_bytes(), b"song data")
            self.assertEqual(json.loads(chart.read_text(encoding="utf-8"))["settings"]["songFilename"], target.name)
            self.assertEqual(bridge.audio_path, str(Path("analysis.wav").resolve()))

    def test_source_equal_to_target_is_reused_without_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            source = output_dir / "song.ogg"
            source.write_bytes(b"same file")

            with mock.patch.object(web_adofai, "_copy_song_atomic") as copy_song:
                _bridge, result = self._export(source, output_dir / "level.adofai")

            self.assertTrue(result["ok"])
            copy_song.assert_not_called()
            self.assertEqual(source.read_bytes(), b"same file")

    def test_identical_existing_target_is_reused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_dir = root / "source"
            output_dir = root / "output"
            source_dir.mkdir()
            output_dir.mkdir()
            source = source_dir / "song.ogg"
            target = output_dir / "song.ogg"
            source.write_bytes(b"identical")
            target.write_bytes(b"identical")

            with mock.patch.object(web_adofai, "_copy_song_atomic") as copy_song:
                _bridge, result = self._export(source, output_dir / "level.adofai")

            self.assertTrue(result["ok"])
            copy_song.assert_not_called()
            self.assertEqual(target.read_bytes(), b"identical")

    def test_different_target_cancels_without_writing_chart_or_audio(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_dir = root / "source"
            output_dir = root / "output"
            source_dir.mkdir()
            output_dir.mkdir()
            source = source_dir / "song.ogg"
            target = output_dir / "song.ogg"
            chart = output_dir / "level.adofai"
            source.write_bytes(b"new")
            target.write_bytes(b"keep")

            _bridge, result = self._export(source, chart, "cancel")

            self.assertFalse(result["ok"])
            self.assertTrue(result["conflict"])
            self.assertEqual(target.read_bytes(), b"keep")
            self.assertFalse(chart.exists())

    def test_rename_uses_available_name_in_file_and_adofai_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_dir = root / "source"
            output_dir = root / "output"
            source_dir.mkdir()
            output_dir.mkdir()
            source = source_dir / "song.ogg"
            (output_dir / "song.ogg").write_bytes(b"keep")
            source.write_bytes(b"new")
            chart = output_dir / "level.adofai"

            _bridge, result = self._export(source, chart, "rename")

            renamed = output_dir / "song (2).ogg"
            self.assertTrue(result["ok"])
            self.assertEqual(renamed.read_bytes(), b"new")
            self.assertEqual(json.loads(chart.read_text(encoding="utf-8"))["settings"]["songFilename"], renamed.name)
            self.assertEqual((output_dir / "song.ogg").read_bytes(), b"keep")

    def test_explicit_overwrite_replaces_target_and_keeps_song_filename(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_dir = root / "source"
            output_dir = root / "output"
            source_dir.mkdir()
            output_dir.mkdir()
            source = source_dir / "song.ogg"
            target = output_dir / "song.ogg"
            source.write_bytes(b"new")
            target.write_bytes(b"old")
            chart = output_dir / "level.adofai"

            _bridge, result = self._export(source, chart, "overwrite")

            self.assertTrue(result["ok"])
            self.assertEqual(target.read_bytes(), b"new")
            self.assertEqual(json.loads(chart.read_text(encoding="utf-8"))["settings"]["songFilename"], target.name)

    def test_atomic_copy_replace_failure_preserves_target_and_cleans_temp(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            source = directory / "source.ogg"
            target = directory / "target.ogg"
            source.write_bytes(b"new")
            target.write_bytes(b"known-good")

            with mock.patch.object(web_adofai.os, "replace", side_effect=OSError("locked")):
                with self.assertRaises(OSError):
                    web_adofai._copy_song_atomic(source, target)

            self.assertEqual(target.read_bytes(), b"known-good")
            self.assertEqual(list(directory.glob(".target.ogg.*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
