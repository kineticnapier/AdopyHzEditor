from __future__ import annotations

from types import SimpleNamespace
import unittest

import numpy as np

from web.track_transcription import _segment_arrays


def _store(times, pitches, strengths):
    return SimpleNamespace(
        track_count=1,
        track_offsets=np.array([0, len(times)], dtype=np.uint64),
        track_start_times=np.array([times[0]], dtype=np.float64),
        track_end_times=np.array([times[-1]], dtype=np.float64),
        point_times=np.asarray(times, dtype=np.float64),
        point_midi=np.asarray(pitches, dtype=np.float64),
        point_magnitudes=np.asarray(strengths, dtype=np.float64),
    )


class TrackTranscriptionZeroWidthClipTests(unittest.TestCase):
    def test_zero_width_clip_uses_pitch_and_strength_at_requested_time(self):
        store = _store([0.0, 1.0], [60.0, 72.0], [0.2, 0.8])
        for at, expected_midi, expected_strength in (
            (0.0, 60.0, 0.2),
            (0.25, 63.0, 0.35),
            (0.75, 69.0, 0.65),
            (1.0, 72.0, 0.8),
        ):
            with self.subTest(at=at):
                segment = _segment_arrays(store, 0, at, at)
                self.assertIsNotNone(segment)
                times, midis, magnitudes, start, end = segment
                self.assertEqual(len(times), 1)
                self.assertAlmostEqual(float(times[0]), at)
                self.assertAlmostEqual(float(midis[0]), expected_midi)
                self.assertAlmostEqual(float(magnitudes[0]), expected_strength)
                self.assertEqual((start, end), (at, at))

    def test_single_point_track_keeps_its_original_values(self):
        store = _store([0.3], [64.0], [0.45])
        segment = _segment_arrays(store, 0, 0.3, 0.3)
        self.assertIsNotNone(segment)
        times, midis, magnitudes, _, _ = segment
        self.assertAlmostEqual(float(times[0]), 0.3)
        self.assertAlmostEqual(float(midis[0]), 64.0)
        self.assertAlmostEqual(float(magnitudes[0]), 0.45)

    def test_fixed_note_conversion_uses_clipped_track_pitch(self):
        from web_ui import Bridge

        bridge = Bridge()
        bridge.frequency_track_store = _store([0.0, 1.0], [60.0, 72.0], [0.2, 0.8])
        bridge.duration = 2.0
        result = bridge.create_notes_from_tracks([0], "fixed", 0.75, 0.75)

        self.assertTrue(result["changed"])
        self.assertEqual(result["indices"], [0])
        self.assertEqual(len(bridge.notes), 1)
        self.assertAlmostEqual(bridge.notes[0].midi, 69.0)
        self.assertAlmostEqual(bridge.notes[0].start, 0.75)
        self.assertGreaterEqual(bridge.notes[0].end, 0.751 - 1e-10)


if __name__ == "__main__":
    unittest.main()
