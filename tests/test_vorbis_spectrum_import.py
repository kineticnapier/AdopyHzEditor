from __future__ import annotations

import base64
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import numpy as np

from core.note_model import Note
from core.vorbis_direct import (
    BackendSelection,
    VorbisSpectrumBlock,
    VorbisSpectrumChannel,
    VorbisStreamInfo,
)
from core.vorbis_spectrum_store import (
    MAX_VIEWPORT_ELEMENTS,
    analyze_vorbis_spectrum_store,
)


class VorbisSpectrumStoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.source = Path(self.temporary.name) / "source.ogg"
        self.source.write_bytes(b"vorbis-test")

    def tearDown(self):
        self.temporary.cleanup()

    @staticmethod
    def _block(
        center_time: float,
        magnitudes: list[float],
        *,
        block_size: int,
        sample_rate: int = 8000,
        next_block_size: int | None = None,
    ) -> VorbisSpectrumBlock:
        values = np.asarray(magnitudes, dtype=np.float32)
        channel = VorbisSpectrumChannel(
            channel=0,
            signed_coefficients=values.copy(),
            magnitude=values.copy(),
            normalized_magnitude=values.copy(),
        )
        return VorbisSpectrumBlock(
            packet_index=int(round(center_time * 1000)),
            mode_index=0,
            start_time=max(0.0, center_time - block_size / (2 * sample_rate)),
            center_time=center_time,
            block_size=block_size,
            sample_rate=sample_rate,
            previous_block_size=block_size,
            next_block_size=next_block_size or block_size,
            granule_position=None,
            channels=(channel,),
        )

    @staticmethod
    def _info(*, short: int = 8, long: int = 16) -> VorbisStreamInfo:
        return VorbisStreamInfo(
            sample_rate=8000,
            channels=1,
            short_block_size=short,
            long_block_size=long,
            total_samples=8000,
        )

    def _store(self):
        blocks = [
            self._block(0.10, [1.0, 0.8, 0.6, 0.1], block_size=8),
            self._block(
                0.20,
                [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8],
                block_size=16,
            ),
        ]
        with mock.patch(
            "core.vorbis_spectrum_store.extract_vorbis_spectrum",
            return_value=(self._info(), iter(blocks)),
        ):
            return analyze_vorbis_spectrum_store(self.source)

    def test_store_keeps_native_bins_without_peak_filtering(self):
        store = self._store()

        self.assertEqual(store.stats.blocks_processed, 2)
        self.assertEqual(store.stats.short_blocks, 1)
        self.assertEqual(store.stats.long_blocks, 1)
        self.assertEqual(store.stats.total_bins, 12)
        self.assertEqual(store.stats.stored_bins, 12)
        self.assertEqual(store.total_bins, 12)
        self.assertTrue(
            all(np.isfinite(plane.magnitudes).all() for plane in store.planes)
        )
        # Descending shoulder values are retained even though they are not
        # local maxima; no temporal tracking or strongest-N filtering occurs.
        np.testing.assert_allclose(store.planes[0].magnitudes[0], [1, 0.8, 0.6, 0.1])

    def test_threshold_filters_query_only(self):
        store = self._store()
        original_count = store.total_bins
        loose = store.query_region(0, 1, 0, 127, 800, 400, 0.0)
        strict = store.query_region(0, 1, 0, 127, 800, 400, 0.75)

        self.assertGreater(loose.returned_elements, strict.returned_elements)
        self.assertEqual(store.total_bins, original_count)

    def test_viewport_filters_time_and_pitch(self):
        store = self._store()
        first = store.query_region(0.05, 0.15, 0, 127, 800, 400, 0.0)
        second = store.query_region(0.15, 0.25, 0, 127, 800, 400, 0.0)
        outside_time = store.query_region(0.5, 0.8, 0, 127, 800, 400, 0.0)
        outside_pitch = store.query_region(0, 1, 120, 127, 800, 400, 0.0)

        self.assertGreater(first.returned_elements, 0)
        self.assertGreater(second.returned_elements, 0)
        self.assertEqual(outside_time.returned_elements, 0)
        self.assertEqual(outside_pitch.returned_elements, 0)

    def test_zoomed_out_query_is_lod_bounded(self):
        info = self._info(short=256, long=2048)
        magnitudes = np.linspace(0.001, 1.0, 1024, dtype=np.float32).tolist()
        blocks = [
            self._block(index * 0.02, magnitudes, block_size=2048)
            for index in range(2000)
        ]
        with mock.patch(
            "core.vorbis_spectrum_store.extract_vorbis_spectrum",
            return_value=(info, iter(blocks)),
        ):
            store = analyze_vorbis_spectrum_store(self.source)

        region = store.query_region(0, 120, 0, 127, 4096, 2048, 0.0)
        self.assertLessEqual(region.returned_elements, MAX_VIEWPORT_ELEMENTS)
        self.assertGreater(region.aggregation_level, 1.0)


class VorbisSpectrumWebIntegrationTests(unittest.TestCase):
    @staticmethod
    def _store():
        case = VorbisSpectrumStoreTests()
        case.setUp()
        store = case._store()
        case.temporary.cleanup()
        return store

    def test_direct_analysis_preserves_notes_and_exposes_spectrum(self):
        import web.backend as web_backend
        from web_ui import Bridge

        bridge = Bridge()
        bridge.audio_path = "tone.ogg"
        bridge.settings["analysisSource"] = "vorbis_direct"
        bridge.notes = [Note(0.0, 0.5, 60.0)]
        bridge._dirty = False
        store = self._store()

        with (
            mock.patch.object(
                web_backend,
                "select_analysis_backend",
                return_value=BackendSelection("vorbis_direct", "vorbis_direct"),
            ),
            mock.patch.object(
                web_backend,
                "analyze_vorbis_spectrum_store",
                return_value=store,
            ),
        ):
            state = bridge.reanalyze_audio()

        self.assertEqual([note.midi for note in bridge.notes], [60.0])
        self.assertIs(bridge.vorbis_spectrum_store, store)
        self.assertEqual(state["analysis"]["source"], "vorbis_direct")
        self.assertTrue(state["analysis"]["available"])
        self.assertEqual(state["view"]["mode"], "both")
        self.assertFalse(state["dirty"])

    def test_region_api_returns_only_packed_viewport_cells(self):
        from web_ui import Bridge

        bridge = Bridge()
        bridge.vorbis_spectrum_store = self._store()
        result = bridge.get_spectrum_region(0, 1, 0, 127, 800, 400, 2.0)

        self.assertTrue(result["available"])
        self.assertGreater(result["recordCount"], 0)
        decoded = base64.b64decode(result["data"])
        self.assertEqual(len(decoded), result["recordCount"] * 5)
        self.assertNotIn("magnitudes", result)


if __name__ == "__main__":
    unittest.main()
