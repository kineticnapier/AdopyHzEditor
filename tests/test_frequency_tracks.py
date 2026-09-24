from __future__ import annotations

import base64
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import numpy as np

from core.frequency_tracks import (
    FrequencyTrackSettings,
    _PACKED_TRACK_POINT_DTYPE,
    build_frequency_track_store,
)
from core.vorbis_direct import VorbisSpectrumBlock, VorbisSpectrumChannel, VorbisStreamInfo
from core.vorbis_spectrum_store import analyze_vorbis_spectrum_store


class FrequencyTrackStoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.source = Path(self.temporary.name) / "tracks.ogg"
        self.source.write_bytes(b"frequency-track-test")

    def tearDown(self):
        self.temporary.cleanup()

    @staticmethod
    def _block(time: float, block_size: int, bins: dict[int, float], sample_rate: int = 8192) -> VorbisSpectrumBlock:
        values = np.zeros(block_size // 2, dtype=np.float32)
        for index, magnitude in bins.items():
            values[index] = magnitude
        channel = VorbisSpectrumChannel(0, values.copy(), values.copy(), values.copy())
        return VorbisSpectrumBlock(
            packet_index=int(round(time * 10_000)), mode_index=0,
            start_time=max(0.0, time - block_size / sample_rate / 2),
            center_time=time, block_size=block_size, sample_rate=sample_rate,
            previous_block_size=block_size, next_block_size=block_size,
            granule_position=None, channels=(channel,),
        )

    def _store(self, blocks: list[VorbisSpectrumBlock], *, short: int = 256, long: int = 1024):
        info = VorbisStreamInfo(8192, 1, short, long, 8192 * 10)
        with mock.patch(
            "core.vorbis_spectrum_store.extract_vorbis_spectrum",
            return_value=(info, iter(blocks)),
        ):
            return analyze_vorbis_spectrum_store(self.source)

    @staticmethod
    def _track_lengths(store) -> np.ndarray:
        return np.diff(store.track_offsets)

    def test_pure_440_hz_makes_one_long_track(self):
        blocks = [self._block(index * 0.02, 1024, {54: 1.0}) for index in range(30)]
        spectrum = self._store(blocks)
        original_bins = spectrum.total_bins
        tracks = build_frequency_track_store(spectrum)
        self.assertEqual(tracks.track_count, 1)
        self.assertEqual(tracks.point_count, 30)
        self.assertGreater(tracks.stats.longest_duration, 0.5)
        self.assertEqual(spectrum.total_bins, original_bins)

    def test_three_simultaneous_tones_make_separate_tracks(self):
        blocks = [self._block(index * 0.02, 1024, {54: 1.0, 82: 0.8, 109: 0.7}) for index in range(20)]
        tracks = build_frequency_track_store(self._store(blocks))
        self.assertEqual(tracks.track_count, 3)
        np.testing.assert_array_equal(self._track_lengths(tracks), [20, 20, 20])

    def test_changing_tone_preserves_the_frequency_path(self):
        blocks = [self._block(index * 0.02, 1024, {54 + index // 4: 1.0}) for index in range(20)]
        tracks = build_frequency_track_store(self._store(blocks))
        longest = int(np.argmax(self._track_lengths(tracks)))
        lo, hi = int(tracks.track_offsets[longest]), int(tracks.track_offsets[longest + 1])
        self.assertEqual(hi - lo, 20)
        self.assertGreater(float(tracks.point_midi[hi - 1]), float(tracks.point_midi[lo]))

    def test_short_and_long_block_mix_does_not_fragment_or_reverse(self):
        blocks = []
        for index in range(30):
            size = 256 if index % 3 else 1024
            # Closest native bin center to 440 Hz for each resolution.
            bin_index = 13 if size == 256 else 54
            blocks.append(self._block(index * 0.018, size, {bin_index: 1.0}))
        tracks = build_frequency_track_store(self._store(blocks))
        self.assertLessEqual(tracks.track_count, 2)
        self.assertGreaterEqual(int(np.max(self._track_lengths(tracks))), 25)
        self.assertTrue(np.all(np.isfinite(tracks.point_times)))
        self.assertTrue(np.all(np.isfinite(tracks.point_midi)))
        for track_id in range(tracks.track_count):
            lo, hi = int(tracks.track_offsets[track_id]), int(tracks.track_offsets[track_id + 1])
            self.assertTrue(np.all(np.diff(tracks.point_times[lo:hi]) >= 0.0))

    def test_nearby_simultaneous_tones_do_not_collapse(self):
        blocks = [self._block(index * 0.02, 1024, {54: 1.0, 57: 0.95}) for index in range(20)]
        tracks = build_frequency_track_store(self._store(blocks))
        self.assertEqual(tracks.track_count, 2)
        np.testing.assert_array_equal(self._track_lengths(tracks), [20, 20])

    def test_viewport_filters_time_and_pitch(self):
        blocks = [self._block(index * 0.02, 1024, {54: 1.0, 82: 0.8}) for index in range(40)]
        tracks = build_frequency_track_store(self._store(blocks))
        region = tracks.query_region(0.2, 0.4, 55.0, 75.0)
        points = np.frombuffer(region.packed_points, dtype=_PACKED_TRACK_POINT_DTYPE)
        self.assertTrue(np.all(points["time"] >= 0.2))
        self.assertTrue(np.all(points["time"] <= 0.4))
        self.assertTrue(np.all(points["midi"] >= 55.0))
        self.assertTrue(np.all(points["midi"] <= 75.0))

    def test_zoomed_out_query_is_point_bounded(self):
        blocks = [
            self._block(index * 0.005, 1024, {20: 1.0, 40: 0.9, 60: 0.8, 80: 0.7})
            for index in range(1000)
        ]
        tracks = build_frequency_track_store(self._store(blocks))
        region = tracks.query_region(0.0, 10.0, 0.0, 127.0, max_points=256)
        self.assertLessEqual(region.returned_points, 256)
        self.assertGreater(region.decimation_level, 1.0)
        self.assertEqual(len(region.packed_points), region.returned_points * _PACKED_TRACK_POINT_DTYPE.itemsize)

    def test_pan_queries_reuse_the_same_generated_store(self):
        blocks = [self._block(index * 0.02, 1024, {54: 1.0}) for index in range(100)]
        tracks = build_frequency_track_store(self._store(blocks))
        fingerprint = tracks.source_fingerprint
        first = tracks.query_region(0.0, 0.5, 0.0, 127.0)
        second = tracks.query_region(0.5, 1.0, 0.0, 127.0)
        self.assertEqual(tracks.source_fingerprint, fingerprint)
        self.assertNotEqual(first.packed_points, second.packed_points)
        self.assertGreater(first.returned_points, 0)
        self.assertGreater(second.returned_points, 0)

    def test_algorithm_parameter_change_builds_a_distinct_store(self):
        blocks = [self._block(index * 0.02, 1024, {54: 1.0}) for index in range(10)]
        spectrum = self._store(blocks)
        default = build_frequency_track_store(spectrum)
        wider = build_frequency_track_store(
            spectrum,
            settings=FrequencyTrackSettings(base_tolerance_cents=100.0),
        )
        self.assertNotEqual(default.source_fingerprint, wider.source_fingerprint)

    def test_web_region_is_packed_and_threshold_does_not_rebuild_tracks(self):
        from web_ui import Bridge

        blocks = [self._block(index * 0.02, 1024, {54: 1.0}) for index in range(30)]
        tracks = build_frequency_track_store(self._store(blocks))
        bridge = Bridge()
        bridge.frequency_track_store = tracks
        original = bridge.frequency_track_store
        bridge.update_settings({"spectrumThreshold": 10.0})
        result = bridge.get_frequency_track_region(0.0, 1.0, 0.0, 127.0, 800, 500)

        self.assertIs(bridge.frequency_track_store, original)
        self.assertTrue(result["available"])
        self.assertGreater(result["trackCount"], 0)
        self.assertGreater(result["pointCount"], 0)
        self.assertEqual(len(base64.b64decode(result["data"])), result["pointCount"] * _PACKED_TRACK_POINT_DTYPE.itemsize)
        self.assertEqual(bridge.analysis_stats["viewportReturnedTrackPoints"], result["pointCount"])


if __name__ == "__main__":
    unittest.main()
