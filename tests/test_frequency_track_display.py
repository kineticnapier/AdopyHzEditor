from __future__ import annotations

from types import SimpleNamespace
import unittest

import numpy as np

from core.frequency_tracks import _PACKED_TRACK_POINT_DTYPE
from web.track_display import display_priority, readable_frequency_track_region


class FrequencyTrackDisplayPolicyTests(unittest.TestCase):
    @staticmethod
    def _store():
        # Three contiguous tracks with deliberately different duration/strength.
        counts = np.array([120, 100, 80], dtype=np.uint64)
        offsets = np.array([0, 120, 220, 300], dtype=np.uint64)
        t0 = np.linspace(0.0, 1.2, 120, dtype=np.float32)
        t1 = np.linspace(0.0, 0.18, 100, dtype=np.float32)
        t2 = np.linspace(0.0, 0.7, 80, dtype=np.float32)
        times = np.concatenate((t0, t1, t2))
        midis = np.concatenate((
            np.full(120, 60.0, dtype=np.float32),
            np.full(100, 64.0, dtype=np.float32),
            np.full(80, 67.0, dtype=np.float32),
        ))
        magnitudes = np.concatenate((
            np.full(120, 0.95, dtype=np.float32),
            np.full(100, 0.18, dtype=np.float32),
            np.full(80, 0.55, dtype=np.float32),
        ))
        return SimpleNamespace(
            point_count=int(times.size),
            point_times=times,
            point_midi=midis,
            point_magnitudes=magnitudes,
            track_offsets=offsets,
            track_start_times=np.array([0.0, 0.0, 0.0], dtype=np.float32),
            track_end_times=np.array([1.2, 0.18, 0.7], dtype=np.float32),
            track_average_magnitudes=np.array([0.95, 0.18, 0.55], dtype=np.float32),
            track_max_magnitudes=np.array([1.0, 0.22, 0.62], dtype=np.float32),
        )

    def test_long_strong_track_has_higher_priority(self):
        strong = display_priority(1.2, 0.95, 1.0)
        weak = display_priority(0.18, 0.18, 0.22)
        self.assertGreater(strong, weak)

    def test_zoomed_in_keeps_all_tracks(self):
        region = readable_frequency_track_region(
            self._store(), 0.0, 5.0, 0.0, 127.0, max_points=400
        )
        points = np.frombuffer(region.packed_points, dtype=_PACKED_TRACK_POINT_DTYPE)
        self.assertEqual(region.returned_tracks, 3)
        self.assertSetEqual(set(map(int, points["track"])), {0, 1, 2})

    def test_normal_view_prefers_high_priority_whole_tracks(self):
        region = readable_frequency_track_region(
            self._store(), 0.0, 12.0, 0.0, 127.0, max_points=256
        )
        points = np.frombuffer(region.packed_points, dtype=_PACKED_TRACK_POINT_DTYPE)
        ids = list(dict.fromkeys(map(int, points["track"])))
        self.assertIn(0, ids)
        self.assertLessEqual(region.returned_points, 256)
        # Selection is whole-track: each returned id occupies one contiguous run.
        for track_id in ids:
            indices = np.flatnonzero(points["track"] == track_id)
            self.assertTrue(np.all(np.diff(indices) == 1))

    def test_same_query_is_deterministic(self):
        store = self._store()
        first = readable_frequency_track_region(store, 0.0, 60.0, 0.0, 127.0, max_points=256)
        second = readable_frequency_track_region(store, 0.0, 60.0, 0.0, 127.0, max_points=256)
        self.assertEqual(first.packed_points, second.packed_points)
        self.assertEqual(first.returned_tracks, second.returned_tracks)


if __name__ == "__main__":
    unittest.main()
