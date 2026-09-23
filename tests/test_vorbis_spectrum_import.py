from __future__ import annotations

import unittest
from unittest import mock

import numpy as np

from core.vorbis_direct import (
    VorbisSpectrumBlock,
    VorbisSpectrumChannel,
    VorbisStreamInfo,
)
from core.vorbis_spectrum_import import (
    VorbisSpectrumImportSettings,
    analyze_vorbis_spectrum_notes,
)


class VorbisSpectrumImportTests(unittest.TestCase):
    @staticmethod
    def _block(
        center_time: float,
        magnitudes: list[float],
        *,
        block_size: int = 8,
        sample_rate: int = 8000,
        next_block_size: int = 8,
    ) -> VorbisSpectrumBlock:
        values = np.asarray(magnitudes, dtype=np.float32)
        norm = float(np.linalg.norm(values.astype(np.float64)))
        normalized = (
            values / norm if norm > np.finfo(np.float32).tiny else np.zeros_like(values)
        ).astype(np.float32)
        channel = VorbisSpectrumChannel(
            channel=0,
            signed_coefficients=values.copy(),
            magnitude=values.copy(),
            normalized_magnitude=normalized,
        )
        return VorbisSpectrumBlock(
            packet_index=int(round(center_time * 1000)),
            mode_index=0,
            start_time=max(0.0, center_time - block_size / (2 * sample_rate)),
            center_time=center_time,
            block_size=block_size,
            sample_rate=sample_rate,
            previous_block_size=block_size,
            next_block_size=next_block_size,
            granule_position=None,
            channels=(channel,),
        )

    @staticmethod
    def _info() -> VorbisStreamInfo:
        return VorbisStreamInfo(
            sample_rate=8000,
            channels=1,
            short_block_size=8,
            long_block_size=16,
            total_samples=8000,
        )

    def test_imports_non_peak_bins_without_pitch_classification(self):
        # 1.0, 0.8 and 0.6 are a descending shoulder. A local-peak detector
        # would keep only the first, while literal spectrum transport keeps all
        # bins that pass the amplitude gate.
        block = self._block(0.1, [1.0, 0.8, 0.6, 0.1])
        with mock.patch(
            "core.vorbis_spectrum_import.extract_vorbis_spectrum",
            return_value=(self._info(), iter([block])),
        ):
            result = analyze_vorbis_spectrum_notes(
                "dummy.ogg",
                settings=VorbisSpectrumImportSettings(
                    minimum_relative_magnitude=0.5,
                ),
            )

        self.assertEqual(len(result.notes), 3)
        self.assertEqual(result.stats.bins_considered, 4)
        self.assertEqual(result.stats.bins_imported, 3)
        self.assertEqual(result.stats.to_dict()["importMode"], "spectrum_bins")

    def test_repeated_bins_are_not_temporally_merged(self):
        blocks = [
            self._block(0.10, [1.0, 0.0, 0.0, 0.0]),
            self._block(0.11, [1.0, 0.0, 0.0, 0.0]),
        ]
        with mock.patch(
            "core.vorbis_spectrum_import.extract_vorbis_spectrum",
            return_value=(self._info(), iter(blocks)),
        ):
            result = analyze_vorbis_spectrum_notes(
                "dummy.ogg",
                settings=VorbisSpectrumImportSettings(
                    minimum_relative_magnitude=0.0,
                ),
            )

        self.assertEqual(len(result.notes), 2)
        self.assertLess(result.notes[0].start, result.notes[1].start)
        self.assertAlmostEqual(result.notes[0].midi, result.notes[1].midi)

    def test_gate_is_amplitude_only(self):
        block = self._block(0.1, [1.0, 0.49, 0.5, 0.0])
        with mock.patch(
            "core.vorbis_spectrum_import.extract_vorbis_spectrum",
            return_value=(self._info(), iter([block])),
        ):
            result = analyze_vorbis_spectrum_notes(
                "dummy.ogg",
                settings=VorbisSpectrumImportSettings(
                    minimum_relative_magnitude=0.5,
                ),
            )

        self.assertEqual(len(result.notes), 2)
        self.assertTrue(all(1 <= note.velocity <= 127 for note in result.notes))

    def test_web_installer_replaces_only_the_experimental_analyzer(self):
        import web.backend as backend
        from web.vorbis_spectrum_import import install_vorbis_spectrum_import
        from core.vorbis_spectrum_import import analyze_vorbis_spectrum_notes

        install_vorbis_spectrum_import()
        self.assertIs(
            backend.analyze_vorbis_direct_notes,
            analyze_vorbis_spectrum_notes,
        )


if __name__ == "__main__":
    unittest.main()
