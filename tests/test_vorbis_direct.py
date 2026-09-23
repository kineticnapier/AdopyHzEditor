from __future__ import annotations

import csv
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import numpy as np

from core.vorbis_direct import (
    VorbisDirectUnavailableError,
    ensure_vorbis_direct_helper,
    extract_vorbis_spectrum,
    select_analysis_backend,
    write_vorbis_spectrum_csv,
)


FFMPEG = shutil.which("ffmpeg")


@unittest.skipUnless(FFMPEG, "ffmpeg is required for Vorbis integration tests")
class VorbisDirectTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.helper = ensure_vorbis_direct_helper()
        except VorbisDirectUnavailableError as exc:
            raise unittest.SkipTest(str(exc)) from exc

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def _encode(self, lavfi: str, name: str, *output_args: str) -> Path:
        output = self.directory / name
        subprocess.run(
            [
                FFMPEG,
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "lavfi",
                "-i",
                lavfi,
                *output_args,
                "-c:a",
                "libvorbis",
                "-q:a",
                "5",
                "-y",
                str(output),
            ],
            check=True,
        )
        return output

    @staticmethod
    def _dominant_frequency(block, channel=0) -> float:
        magnitudes = block.channels[channel].normalized_magnitude
        return float(block.bin_frequencies_hz[int(np.argmax(magnitudes))])

    def test_pure_tone_peak_and_bin_frequency(self):
        source = self._encode(
            "sine=frequency=440:sample_rate=44100:duration=1",
            "tone.ogg",
        )
        info, iterator = extract_vorbis_spectrum(
            source, helper_path=self.helper
        )
        blocks = [
            block
            for block in iterator
            if block.block_size == info.long_block_size
            and 0.1 <= block.center_time <= 0.9
        ]
        peaks = [self._dominant_frequency(block) for block in blocks]

        self.assertTrue(peaks)
        self.assertLess(abs(float(np.median(peaks)) - 440.0), 25.0)
        expected_first_bin = 0.5 * info.sample_rate / info.long_block_size
        self.assertAlmostEqual(
            blocks[0].bin_frequencies_hz[0],
            expected_first_bin,
            places=10,
        )
        self.assertTrue(
            all(
                np.isclose(
                    np.sum(
                        block.channels[0].normalized_magnitude.astype(
                            np.float64
                        )
                        ** 2
                    ),
                    1.0,
                    atol=1e-5,
                )
                for block in blocks
            )
        )

    def test_multiple_tones_produce_multiple_local_peaks(self):
        source = self._encode(
            (
                "aevalsrc="
                "0.25*sin(2*PI*440*t)+"
                "0.2*sin(2*PI*660*t)+"
                "0.15*sin(2*PI*880*t):s=44100:d=1.5"
            ),
            "multiple.ogg",
        )
        info, iterator = extract_vorbis_spectrum(
            source, helper_path=self.helper
        )
        spectra = [
            block.channels[0].normalized_magnitude
            for block in iterator
            if block.block_size == info.long_block_size
            and 0.2 <= block.center_time <= 1.2
        ]
        median = np.median(np.stack(spectra), axis=0)
        frequencies = (
            np.arange(len(median), dtype=np.float64) + 0.5
        ) * info.sample_rate / info.long_block_size
        for target in (440.0, 660.0, 880.0):
            near = np.abs(frequencies - target) <= 25.0
            self.assertGreater(float(np.max(median[near])), 0.08)

    def test_variable_blocks_have_continuous_overlap_timing(self):
        source = self._encode(
            (
                "aevalsrc="
                "0.2*sin(2*PI*440*t)+"
                "if(lt(mod(t\\,0.25)\\,0.001)\\,0.8\\,0)"
                ":s=44100:d=2"
            ),
            "transient.ogg",
        )
        info, iterator = extract_vorbis_spectrum(
            source, helper_path=self.helper
        )
        blocks = list(iterator)
        sizes = {block.block_size for block in blocks}
        self.assertEqual(
            sizes, {info.short_block_size, info.long_block_size}
        )

        for previous, current in zip(blocks, blocks[1:]):
            expected = (
                previous.block_size + current.block_size
            ) / (4.0 * info.sample_rate)
            self.assertAlmostEqual(
                current.center_time - previous.center_time,
                expected,
                places=10,
            )
            self.assertEqual(
                current.previous_block_size, previous.block_size
            )
            self.assertEqual(
                previous.next_block_size, current.block_size
            )
            for channel in current.channels:
                self.assertTrue(np.all(np.isfinite(channel.magnitude)))

        self.assertEqual(blocks[-1].granule_position, info.total_samples)

    def test_stereo_is_reconstructed_after_inverse_coupling(self):
        source = self.directory / "stereo.ogg"
        subprocess.run(
            [
                FFMPEG,
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=440:sample_rate=44100:duration=1",
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=880:sample_rate=44100:duration=1",
                "-filter_complex",
                "[0:a][1:a]amerge=inputs=2",
                "-ac",
                "2",
                "-c:a",
                "libvorbis",
                "-q:a",
                "5",
                "-y",
                str(source),
            ],
            check=True,
        )
        info, iterator = extract_vorbis_spectrum(
            source, helper_path=self.helper
        )
        blocks = [
            block
            for block in iterator
            if block.block_size == info.long_block_size
            and 0.2 <= block.center_time <= 0.8
        ]
        left = np.median(
            [self._dominant_frequency(block, 0) for block in blocks]
        )
        right = np.median(
            [self._dominant_frequency(block, 1) for block in blocks]
        )
        self.assertLess(abs(float(left) - 440.0), 25.0)
        self.assertLess(abs(float(right) - 880.0), 25.0)

    def test_csv_dump_contains_raw_and_normalized_coefficients(self):
        source = self._encode(
            "sine=frequency=440:sample_rate=8000:duration=0.05",
            "short.ogg",
        )
        _, blocks = extract_vorbis_spectrum(
            source, helper_path=self.helper
        )
        output = self.directory / "spectrum.csv"
        write_vorbis_spectrum_csv(blocks, output)
        with output.open(encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream)
            row = next(reader)
        self.assertEqual(
            set(row),
            {
                "time",
                "start_time",
                "center_time",
                "block_size",
                "previous_block_size",
                "next_block_size",
                "channel",
                "bin",
                "frequency_hz",
                "signed_coefficient",
                "magnitude",
                "normalized_magnitude",
            },
        )

    def test_non_vorbis_selection_falls_back_without_decoding(self):
        source = self.directory / "audio.wav"
        source.write_bytes(b"RIFF" + b"\0" * 64)
        selection = select_analysis_backend(source, "vorbis_direct")
        self.assertEqual(selection.requested, "vorbis_direct")
        self.assertEqual(selection.selected, "pcm")
        self.assertIn("falling back", selection.fallback_reason)


if __name__ == "__main__":
    unittest.main()
