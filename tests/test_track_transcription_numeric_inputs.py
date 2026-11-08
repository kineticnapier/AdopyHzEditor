from __future__ import annotations

import unittest
from types import SimpleNamespace

import numpy as np

from web_ui import Bridge


def _store():
    return SimpleNamespace(
        track_count=1,
        track_offsets=np.array([0, 2], dtype=np.uint64),
        track_start_times=np.array([0.0], dtype=np.float64),
        track_end_times=np.array([1.0], dtype=np.float64),
        point_times=np.array([0.0, 1.0], dtype=np.float64),
        point_midi=np.array([60.0, 72.0], dtype=np.float64),
        point_magnitudes=np.array([0.2, 0.8], dtype=np.float64),
    )


class TrackTranscriptionNumericInputTests(unittest.TestCase):
    def setUp(self):
        self.bridge = Bridge()
        self.bridge.frequency_track_store = _store()
        self.bridge.duration = 2.0

    def test_find_tracks_rejects_nonfinite_rectangle_coordinates(self):
        valid = (0.0, 1.0, 0.0, 127.0)
        for position in range(4):
            for invalid in (float("nan"), float("inf"), float("-inf")):
                args = list(valid)
                args[position] = invalid
                with self.subTest(position=position, invalid=invalid):
                    with self.assertRaisesRegex(ValueError, "must be finite"):
                        self.bridge.find_frequency_tracks(*args)

    def test_conversion_rejects_nonfinite_clip_without_editing_notes(self):
        for mode in ("fixed", "curve"):
            for start, end in (
                (float("nan"), None),
                (None, float("nan")),
                (float("inf"), 1.0),
                (0.0, float("-inf")),
            ):
                with self.subTest(mode=mode, start=start, end=end):
                    with self.assertRaisesRegex(ValueError, "must be finite"):
                        self.bridge.create_notes_from_tracks([0], mode, start, end)
                    self.assertEqual(self.bridge.notes, [])

    def test_boolean_track_id_does_not_select_track_zero(self):
        result = self.bridge.create_notes_from_tracks([False], "fixed", 0.0, 1.0)
        self.assertFalse(result["changed"])
        self.assertEqual(result["indices"], [])
        self.assertEqual(self.bridge.notes, [])

    def test_find_tracks_rejects_rectangles_outside_audio_time(self):
        self.bridge.duration = 1.0
        for start, end in ((-3.0, -1.0), (2.0, 3.0)):
            with self.subTest(start=start, end=end):
                result = self.bridge.find_frequency_tracks(start, end, 0.0, 127.0)
                self.assertEqual(result["trackIds"], [])

    def test_find_tracks_rejects_rectangles_outside_midi_bounds(self):
        self.bridge.duration = 1.0
        for pitch, minimum, maximum in ((0.0, -20.0, -5.0), (127.0, 130.0, 150.0)):
            with self.subTest(pitch=pitch):
                self.bridge.frequency_track_store.point_midi[:] = pitch
                result = self.bridge.find_frequency_tracks(0.0, 1.0, minimum, maximum)
                self.assertEqual(result["trackIds"], [])

    def test_find_tracks_normalizes_reversed_rectangle_bounds(self):
        self.bridge.duration = 1.0
        result = self.bridge.find_frequency_tracks(0.8, 0.2, 75.0, 65.0)
        self.assertEqual(result["trackIds"], [0])

    def test_conversion_rejects_clips_fully_outside_audio(self):
        self.bridge.duration = 1.0
        for mode in ("fixed", "curve"):
            for start, end in ((-3.0, -1.0), (-1.0, -3.0), (2.0, 3.0), (3.0, 2.0)):
                with self.subTest(mode=mode, start=start, end=end):
                    result = self.bridge.create_notes_from_tracks([0], mode, start, end)
                    self.assertFalse(result["changed"])
                    self.assertEqual(result["indices"], [])
                    self.assertEqual(self.bridge.notes, [])

    def test_finite_clip_still_converts_requested_track(self):
        result = self.bridge.create_notes_from_tracks([0], "fixed", 0.75, 0.75)
        self.assertTrue(result["changed"])
        self.assertEqual(result["indices"], [0])
        self.assertAlmostEqual(self.bridge.notes[0].midi, 69.0)


if __name__ == "__main__":
    unittest.main()
