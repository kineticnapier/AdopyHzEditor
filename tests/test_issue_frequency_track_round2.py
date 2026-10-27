from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest import mock

import numpy as np

import web.track_display as track_display
from core.frequency_tracks import _PACKED_TRACK_POINT_DTYPE
from web.track_transcription import _intersects_track_rect


def _three_track_store(fingerprint: str):
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
        track_count=3,
        track_offsets=offsets,
        track_start_times=np.array([0.0, 0.0, 0.0], dtype=np.float32),
        track_end_times=np.array([1.2, 0.18, 0.7], dtype=np.float32),
        track_average_magnitudes=np.array([0.95, 0.18, 0.55], dtype=np.float32),
        track_max_magnitudes=np.array([1.0, 0.22, 0.62], dtype=np.float32),
        source_fingerprint=(fingerprint,),
    )


class FrequencyTrackRound2Tests(unittest.TestCase):
    def test_diagonal_segment_outside_time_clipped_pitch_is_not_selected(self):
        store = SimpleNamespace(
            track_count=1,
            track_offsets=np.array([0, 2], dtype=np.uint64),
            point_times=np.array([0.0, 0.04], dtype=np.float32),
            point_midi=np.array([60.0, 61.0], dtype=np.float32),
        )
        self.assertFalse(
            _intersects_track_rect(
                store,
                0,
                0.0,
                0.01,
                60.8,
                60.9,
            )
        )

    def test_diagonal_segment_is_selected_when_clipped_segment_crosses_rect(self):
        store = SimpleNamespace(
            track_count=1,
            track_offsets=np.array([0, 2], dtype=np.uint64),
            point_times=np.array([0.0, 0.04], dtype=np.float32),
            point_midi=np.array([60.0, 61.0], dtype=np.float32),
        )
        self.assertTrue(
            _intersects_track_rect(
                store,
                0,
                0.02,
                0.03,
                60.6,
                60.8,
            )
        )

    def test_short_view_skips_continuity_ranking(self):
        store = _three_track_store("short-no-continuity")
        with mock.patch.object(
            track_display,
            "track_continuity",
            wraps=track_display.track_continuity,
        ) as continuity:
            region = track_display.readable_frequency_track_region(
                store, 0.0, 5.0, 0.0, 127.0, max_points=400
            )

        self.assertEqual(region.returned_tracks, 3)
        continuity.assert_not_called()

    def test_long_view_reuses_track_continuity_by_store_fingerprint(self):
        store = _three_track_store("long-continuity-cache")
        with mock.patch.object(
            track_display,
            "track_continuity",
            wraps=track_display.track_continuity,
        ) as continuity:
            first = track_display.readable_frequency_track_region(
                store, 0.0, 12.0, 0.0, 127.0, max_points=400
            )
            first_calls = continuity.call_count
            second = track_display.readable_frequency_track_region(
                store, 0.0, 12.0, 0.0, 127.0, max_points=400
            )

        self.assertGreater(first_calls, 0)
        self.assertEqual(continuity.call_count, first_calls)
        self.assertEqual(first.packed_points, second.packed_points)

    def test_short_single_point_tracks_never_exceed_point_budget(self):
        count = 301
        store = SimpleNamespace(
            point_count=count,
            point_times=np.zeros(count, dtype=np.float32),
            point_midi=np.full(count, 60.0, dtype=np.float32),
            point_magnitudes=np.full(count, 0.5, dtype=np.float32),
            track_count=count,
            track_offsets=np.arange(count + 1, dtype=np.uint64),
            track_start_times=np.zeros(count, dtype=np.float32),
            track_end_times=np.zeros(count, dtype=np.float32),
            track_average_magnitudes=np.full(count, 0.5, dtype=np.float32),
            track_max_magnitudes=np.full(count, 0.5, dtype=np.float32),
            source_fingerprint=("short-budget-overflow",),
        )

        region = track_display.readable_frequency_track_region(
            store, 0.0, 5.0, 0.0, 127.0, max_points=256
        )
        points = np.frombuffer(
            region.packed_points,
            dtype=_PACKED_TRACK_POINT_DTYPE,
        )

        self.assertLessEqual(region.returned_points, 256)
        self.assertLessEqual(len(points), 256)
        self.assertEqual(region.returned_tracks, 256)
        np.testing.assert_array_equal(
            points["track"],
            np.arange(256, dtype=np.uint32),
        )


if __name__ == "__main__":
    unittest.main()
