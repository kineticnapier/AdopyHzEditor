from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from mido import MidiFile

from core.note_model import Note
from exporters.midi import export_midi


class AtomicMidiExportTests(unittest.TestCase):
    def test_normal_export_replaces_existing_file_with_valid_midi(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "notes.mid"
            target.write_bytes(b"old midi")
            export_midi([Note(0.0, 0.5, 60)], target, bpm=120)
            parsed = MidiFile(target)
        self.assertEqual(parsed.ticks_per_beat, 480)
        self.assertTrue(any(message.type == "note_on" for message in parsed.tracks[0]))

    def test_write_failure_preserves_existing_file_and_cleans_temp(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "notes.mid"
            original = b"existing midi bytes"
            target.write_bytes(original)

            def fail_save(_midi, filename):
                Path(filename).write_bytes(b"partial")
                raise OSError("disk full")

            with (
                mock.patch.object(MidiFile, "save", autospec=True, side_effect=fail_save),
                self.assertRaisesRegex(OSError, "disk full"),
            ):
                export_midi([Note(0.0, 0.5, 60)], target)

            self.assertEqual(target.read_bytes(), original)
            self.assertEqual(list(Path(tmp).iterdir()), [target])

    def test_replace_failure_preserves_existing_file_and_cleans_temp(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "notes.mid"
            original = b"existing midi bytes"
            target.write_bytes(original)
            with (
                mock.patch.object(os, "replace", side_effect=OSError("locked")),
                self.assertRaisesRegex(OSError, "locked"),
            ):
                export_midi([Note(0.0, 0.5, 60)], target)
            self.assertEqual(target.read_bytes(), original)
            self.assertEqual(list(Path(tmp).iterdir()), [target])


if __name__ == "__main__":
    unittest.main()
