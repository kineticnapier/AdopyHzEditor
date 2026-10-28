from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
from mido import MidiFile

from core.audio_player import AudioPlayer, PreviewSegment
from core.audio_analysis import Spectrogram
from core.note_model import Note
from exporters.midi import export_midi
from web.backend import Bridge


class NewIssueRegressionTests(unittest.TestCase):
    def bridge(self) -> Bridge:
        bridge = Bridge()
        bridge.duration = 2.0
        bridge.player.set_virtual_duration(2.0)
        bridge.notes = [Note(0.3, 0.5, 60)]
        bridge.settings.update(snapEnabled=True, bpm=120.0, snapDiv=1, offsetMs=0.0)
        bridge._undo_stack.clear()
        bridge._redo_stack.clear()
        bridge._dirty = False
        return bridge

    def test_failed_midi_write_preserves_existing_target_and_cleans_temporary(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "existing.mid"
            target.write_bytes(b"original midi bytes")

            def fail_after_partial_write(_self, filename):
                Path(filename).write_bytes(b"partial")
                raise OSError("disk full")

            with mock.patch.object(MidiFile, "save", autospec=True, side_effect=fail_after_partial_write):
                with self.assertRaises(OSError):
                    export_midi([Note(0, 1, 60)], target)

            self.assertEqual(target.read_bytes(), b"original midi bytes")
            self.assertEqual(list(Path(directory).glob(".existing.mid.*.tmp")), [])

    def test_snap_midpoint_matches_javascript_math_round(self):
        bridge = self.bridge()
        # 0.25 is exactly halfway between 0 and 0.5; Math.round chooses 0.5.
        self.assertEqual(bridge._snap_time(0.25), 0.5)

    def test_vertical_move_does_not_snap_time_and_reports_real_change(self):
        bridge = self.bridge()
        result = bridge.move_notes([0], 0.0, 1.0)
        moved = Note.from_dict(result["notes"][0])
        self.assertEqual((moved.start, moved.end, moved.midi), (0.3, 0.5, 61.0))
        self.assertTrue(result["changed"])

    def test_boundary_noop_preserves_history_redo_and_dirty(self):
        bridge = self.bridge()
        bridge.notes = [Note(0.0, 0.5, 0.0)]
        sentinel = bridge._snapshot()
        bridge._redo_stack.append(sentinel)

        result = bridge.move_notes([0], -1.0, -1.0)

        self.assertFalse(result["changed"])
        self.assertEqual(bridge._undo_stack, [])
        self.assertEqual(bridge._redo_stack, [sentinel])
        self.assertFalse(bridge._dirty)

    def test_octave_shift_scales_stored_curve_phase(self):
        player = AudioPlayer()
        player.sr = 1000
        player.note_sound_enabled = True
        player.note_volume = 1.0
        player.note_octave_shift = 1
        player.preview_notes = [PreviewSegment(10, 20, 60.0, phase=0.3, fade_in=False, fade_out=False)]
        player._preview_ends = [20]
        output = np.zeros((1, 1), dtype=np.float32)

        player._mix_preview_notes(output, np.array([10.0]))

        self.assertAlmostEqual(float(output[0, 0]), float(np.sin(0.6)), places=6)

    def test_fit_near_chart_end_keeps_view_inside_duration(self):
        bridge = self.bridge()
        bridge.duration = 60.0
        bridge.notes = [Note(59.0, 60.0, 60)]
        fitted = bridge.fit_view()
        self.assertLessEqual(fitted["start"] + fitted["windowSeconds"], 60.0 + 1e-12)

    def test_view_pitch_range_never_exceeds_midi_domain(self):
        bridge = self.bridge()
        view = bridge.set_view({"pitchBottom": 120, "visibleNotes": 60})
        self.assertLessEqual(view["pitchBottom"] + view["visibleNotes"], 128)

    def test_cqt_request_returns_only_requested_pitch_rows(self):
        bridge = self.bridge()
        bridge.spectrogram = Spectrogram(
            audio_path="range.wav",
            db=np.zeros((128, 10), dtype=np.float32),
            duration=2.0,
            midi_min=0,
            midi_max=127,
            frame_times=np.linspace(0.0, 2.0, 10),
            sr=44_100,
        )
        result = bridge.get_spectrogram(64, 0.0, 2.0, 60.0, 72.0)
        self.assertLessEqual(result["rows"], 14)
        self.assertLessEqual(result["midiMin"], 60.0)
        self.assertGreaterEqual(result["midiMax"], 72.0)

    def test_undo_back_to_saved_checkpoint_clears_dirty(self):
        bridge = self.bridge()
        bridge._saved_checkpoint = bridge._document_checkpoint()
        bridge._dirty = False
        bridge.move_notes([0], 0.5, 0.0)
        self.assertTrue(bridge._dirty)

        result = bridge.undo()

        self.assertFalse(result["dirty"])
        self.assertFalse(bridge._dirty)


if __name__ == "__main__":
    unittest.main()
