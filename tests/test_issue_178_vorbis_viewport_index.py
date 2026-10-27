from __future__ import annotations

import unittest

import numpy as np

from core.vorbis_spectrum_store import _cached_bin_midi, _candidate_time_bounds


class VorbisViewportIndexTests(unittest.TestCase):
    def test_narrow_view_uses_small_time_candidate_slice(self):
        centers = np.arange(100_000, dtype=np.float64) * 0.01
        spans = np.full(centers.shape, 0.08, dtype=np.float32)
        start, end, maximum_span = 500.0, 500.10, 0.08

        left, right = _candidate_time_bounds(
            centers, start, end, maximum_span
        )
        candidate_centers = centers[left:right]
        candidate_spans = spans[left:right]
        candidate_visible = np.flatnonzero(
            (candidate_centers <= end)
            & (candidate_centers + candidate_spans >= start)
        ) + left
        naive_visible = np.flatnonzero(
            (centers <= end) & (centers + spans >= start)
        )

        self.assertLess(right - left, 32)
        np.testing.assert_array_equal(candidate_visible, naive_visible)

    def test_candidate_window_keeps_block_that_starts_before_view(self):
        centers = np.array([0.90, 0.96, 1.04, 1.20], dtype=np.float64)
        spans = np.array([0.05, 0.10, 0.04, 0.02], dtype=np.float32)

        left, right = _candidate_time_bounds(centers, 1.0, 1.05, 0.10)
        candidate = np.arange(left, right)
        visible = candidate[
            (centers[candidate] <= 1.05)
            & (centers[candidate] + spans[candidate] >= 1.0)
        ]

        np.testing.assert_array_equal(visible, np.array([1, 2]))

    def test_bin_midi_table_is_cached_per_native_block_size(self):
        first = _cached_bin_midi(48_000, 2048)
        second = _cached_bin_midi(48_000, 2048)
        other = _cached_bin_midi(48_000, 1024)

        self.assertIs(first, second)
        self.assertIsNot(first, other)
        self.assertFalse(first.flags.writeable)
        self.assertEqual(first.shape, (1024,))


if __name__ == "__main__":
    unittest.main()
