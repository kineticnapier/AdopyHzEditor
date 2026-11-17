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


    def test_resize_at_time_bounds_does_not_pollute_undo_or_redo(self):
        for note, edge, delta in (
            (Note(0.0, 1.0, 60.0), "start", -2.0),
            (Note(9.0, 10.0, 60.0), "end", 2.0),
        ):
            with self.subTest(edge=edge):
                bridge = Bridge()
                bridge.duration = 10.0
                bridge.notes = [note.normalized()]
                original = list(bridge.notes)
                bridge._redo_stack.append(bridge._snapshot())
                result = bridge.resize_notes([0], edge, delta)
                self.assertIs(result["changed"], False)
                self.assertEqual(bridge.notes, original)
                self.assertFalse(bridge._dirty)
                self.assertEqual(len(bridge._undo_stack), 0)
                self.assertEqual(len(bridge._redo_stack), 1)

    def test_resize_snapped_to_same_time_is_noop(self):
        bridge = Bridge()
        bridge.duration = 10.0
        bridge.notes = [Note(1.0, 2.0, 60.0).normalized()]
        bridge.settings.update(snapEnabled=True, bpm=120.0, snapDiv=1, offsetMs=0.0)
        result = bridge.resize_notes([0], "start", 0.1)
        self.assertIs(result["changed"], False)
        self.assertEqual(bridge.notes[0].start, 1.0)
        self.assertEqual(len(bridge._undo_stack), 0)
        self.assertFalse(bridge._dirty)

    def test_resize_real_change_keeps_single_undo_and_restores_saved_state(self):
        bridge = Bridge()
        bridge.duration = 10.0
        bridge.notes = [Note(1.0, 2.0, 60.0).normalized()]
        bridge._saved_checkpoint = bridge._document_checkpoint()
        bridge._redo_stack.append(bridge._snapshot())
        result = bridge.resize_notes([0], "start", 0.25)
        self.assertIs(result["changed"], True)
        self.assertAlmostEqual(bridge.notes[0].start, 1.25)
        self.assertTrue(bridge._dirty)
        self.assertEqual(len(bridge._undo_stack), 1)
        self.assertEqual(len(bridge._redo_stack), 0)
        bridge.undo()
        self.assertAlmostEqual(bridge.notes[0].start, 1.0)
        self.assertFalse(bridge._dirty)

    def test_resize_mixed_selection_commits_only_when_one_note_moves(self):
        bridge = Bridge()
        bridge.duration = 10.0
        bridge.notes = [
            Note(0.0, 1.0, 60.0).normalized(),
            Note(2.0, 3.0, 64.0).normalized(),
        ]
        result = bridge.resize_notes([0, 1], "start", -0.5)
        self.assertIs(result["changed"], True)
        self.assertEqual(bridge.notes[0].start, 0.0)
        self.assertEqual(bridge.notes[1].start, 1.5)
        self.assertEqual(len(bridge._undo_stack), 1)


if __name__ == "__main__":
    unittest.main()
