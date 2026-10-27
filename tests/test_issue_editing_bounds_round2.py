from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest import mock

import web.tools as web_tools
from core.note_model import Note
from web_ui import Bridge


class EditingBoundsRound2Tests(unittest.TestCase):
    def test_direct_audio_merge_keeps_audio_duration_and_bounds(self):
        bridge = Bridge()
        bridge.audio_path = str(Path("song.ogg").resolve())
        bridge.spectrogram = None
        bridge.vorbis_spectrum_store = SimpleNamespace(duration=180.0)
        bridge.duration = 180.0
        bridge.midi_min = 0
        bridge.midi_max = 127
        bridge.notes = [Note(5.0, 6.0, 60.0).normalized()]
        incoming = [Note(20.0, 30.0, 72.0).normalized()]

        with (
            mock.patch.object(bridge, "_dialog", return_value="notes.adopyhz"),
            mock.patch.object(web_tools, "load_project", return_value=(None, incoming, {})),
        ):
            bridge.merge_project_notes_dialog()

        self.assertEqual(bridge.duration, 180.0)
        self.assertEqual((bridge.midi_min, bridge.midi_max), (0, 127))
        self.assertIsNotNone(bridge.vorbis_spectrum_store)
        self.assertEqual(len(bridge.notes), 2)

    def test_blank_workspace_cannot_hide_preserved_tail_notes(self):
        bridge = Bridge()
        bridge.notes = [Note(25.0, 26.0, 60.0).normalized()]

        bridge.apply_blank_workspace({"duration": 10.0, "midiMin": 12, "midiMax": 108})

        self.assertEqual(bridge.duration, 26.0)
        self.assertGreaterEqual(bridge.player.duration, 26.0)
        view = bridge.set_view({"start": 24.0, "windowSeconds": 2.0})
        self.assertGreaterEqual(view["start"], 24.0)

    def test_duplicate_zero_pitch_delta_preserves_notes_outside_analysis_range(self):
        bridge = Bridge()
        bridge.duration = 10.0
        bridge.midi_min = 12
        bridge.midi_max = 120
        bridge.notes = [Note(1.0, 2.0, 5.0).normalized()]

        result = bridge.duplicate_notes_shifted([0], 1.0, 0.0)

        self.assertEqual(len(result["indices"]), 1)
        self.assertAlmostEqual(bridge.notes[result["indices"][0]].midi, 5.0)

    def test_bulk_zero_pitch_delta_preserves_notes_outside_analysis_range(self):
        bridge = Bridge()
        bridge.duration = 10.0
        bridge.midi_min = 12
        bridge.midi_max = 120
        bridge.notes = [
            Note(1.0, 2.0, 5.0).normalized(),
            Note(3.0, 4.0, 125.0).normalized(),
        ]

        bridge.bulk_edit_notes([0, 1], {"timeDelta": 1.0, "pitchDelta": 0.0})

        self.assertAlmostEqual(bridge.notes[0].midi, 5.0)
        self.assertAlmostEqual(bridge.notes[1].midi, 125.0)
        self.assertAlmostEqual(bridge.notes[0].start, 2.0)
        self.assertAlmostEqual(bridge.notes[1].start, 4.0)


if __name__ == "__main__":
    unittest.main()
