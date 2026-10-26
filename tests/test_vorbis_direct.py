from __future__ import annotations

import csv
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

import numpy as np

from core.audio_analysis import Spectrogram
from core.note_model import Note
from core.vorbis_direct import (
    analyze_vorbis_direct_notes,
    BackendSelection,
    VorbisDirectAnalysisStats,
    VorbisDirectNoteResult,
    VorbisDirectUnavailableError,
    VorbisStreamInfo,
    ensure_vorbis_direct_helper,
    extract_vorbis_spectrum,
    select_analysis_backend,
    write_vorbis_spectrum_csv,
)
from core.vorbis_spectrum_store import analyze_vorbis_spectrum_store


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

    def test_pure_tone_is_retained_in_compact_spectrum_store(self):
        source = self._encode(
            "sine=frequency=440:sample_rate=44100:duration=1",
            "stored-tone.ogg",
        )
        store = analyze_vorbis_spectrum_store(
            source,
            helper_path=self.helper,
        )
        long_plane = next(
            plane
            for plane in store.planes
            if plane.block_size == store.stream_info.long_block_size
        )
        frequencies = (
            np.arange(long_plane.magnitudes.shape[1], dtype=np.float64) + 0.5
        ) * store.stream_info.sample_rate / long_plane.block_size
        evidence = np.max(long_plane.magnitudes, axis=0)

        self.assertGreater(store.stats.stored_bins, 0)
        self.assertEqual(store.stats.stored_bins, store.stats.total_bins)
        self.assertLess(
            abs(float(frequencies[int(np.argmax(evidence))]) - 440.0),
            25.0,
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

    def test_pure_tone_becomes_a_small_number_of_long_notes(self):
        source = self._encode(
            "sine=frequency=440:sample_rate=44100:duration=3",
            "tracked-tone.ogg",
        )

        result = analyze_vorbis_direct_notes(
            source,
            helper_path=self.helper,
        )
        near_440 = [
            note for note in result.notes if abs(note.freq - 440.0) < 25.0
        ]

        self.assertTrue(near_440)
        self.assertGreater(max(note.duration for note in near_440), 2.5)
        self.assertLess(len(result.notes), result.stats.blocks_processed // 4)
        self.assertEqual(result.stats.final_note_count, len(result.notes))

    def test_multiple_tones_become_simultaneous_notes(self):
        source = self._encode(
            (
                "aevalsrc="
                "0.25*sin(2*PI*440*t)+"
                "0.2*sin(2*PI*660*t)+"
                "0.15*sin(2*PI*880*t):s=44100:d=2"
            ),
            "tracked-multiple.ogg",
        )

        result = analyze_vorbis_direct_notes(
            source,
            helper_path=self.helper,
        )

        for frequency in (440.0, 660.0, 880.0):
            matching = [
                note
                for note in result.notes
                if abs(note.freq - frequency) < 30.0 and note.duration > 1.5
            ]
            self.assertTrue(matching, frequency)

    def test_changing_tone_tracks_frequency_and_time(self):
        source = self._encode(
            (
                "aevalsrc="
                "if(lt(t\\,1)\\,sin(2*PI*440*t)\\,"
                "sin(2*PI*660*t)):s=44100:d=2"
            ),
            "changing.ogg",
        )

        result = analyze_vorbis_direct_notes(
            source,
            helper_path=self.helper,
        )
        first = [
            note
            for note in result.notes
            if abs(note.freq - 440.0) < 30.0 and note.start < 0.2
        ]
        second = [
            note
            for note in result.notes
            if abs(note.freq - 660.0) < 30.0 and note.start > 0.8
        ]

        self.assertTrue(first)
        self.assertTrue(second)
        self.assertLess(min(note.start for note in second), 1.2)

    def test_note_analysis_accepts_short_and_long_blocks(self):
        source = self._encode(
            (
                "aevalsrc="
                "0.2*sin(2*PI*440*t)+"
                "if(lt(mod(t\\,0.25)\\,0.001)\\,0.8\\,0)"
                ":s=44100:d=2"
            ),
            "tracked-transient.ogg",
        )

        result = analyze_vorbis_direct_notes(
            source,
            helper_path=self.helper,
        )

        self.assertGreater(result.stats.short_blocks, 0)
        self.assertGreater(result.stats.long_blocks, 0)
        self.assertEqual(
            result.stats.blocks_processed,
            result.stats.short_blocks + result.stats.long_blocks,
        )
        previous_start = -1.0
        for note in result.notes:
            self.assertTrue(np.isfinite([note.start, note.end, note.midi]).all())
            self.assertGreater(note.end, note.start)
            self.assertGreaterEqual(note.start, previous_start)
            previous_start = note.start


class VorbisDirectEditorIntegrationTests(unittest.TestCase):
    def test_non_vorbis_direct_request_falls_back_without_replacing_notes(self):
        import web.backend as web_backend
        from web_ui import Bridge

        bridge = Bridge()
        bridge.audio_path = "audio.wav"
        bridge.settings["analysisSource"] = "vorbis_direct"
        bridge.notes = [Note(0.0, 0.5, 60.0)]
        spec = Spectrogram(
            audio_path="audio.wav",
            db=np.zeros((2, 3), dtype=np.float32),
            duration=1.0,
            midi_min=60,
            midi_max=61,
            frame_times=np.linspace(0.0, 1.0, 3),
            sr=22050,
            bins_per_semitone=1,
        )

        with (
            mock.patch.object(
                web_backend,
                "select_analysis_backend",
                return_value=mock.Mock(
                    selected="pcm",
                    fallback_reason="not Vorbis",
                ),
            ),
            mock.patch.object(web_backend, "analyze_cqt", return_value=spec),
        ):
            state = bridge.reanalyze_audio()

        self.assertEqual([note.midi for note in bridge.notes], [60.0])
        self.assertTrue(state["analysis"]["available"])
        self.assertEqual(state["analysis"]["stats"]["selectedSource"], "cqt")
        self.assertEqual(state["analysis"]["stats"]["fallbackReason"], "not Vorbis")

    def test_default_cqt_path_is_unchanged(self):
        import web.backend as web_backend
        from web_ui import Bridge

        bridge = Bridge()
        bridge.audio_path = "audio.ogg"
        original_notes = [Note(0.0, 0.5, 60.0)]
        bridge.notes = list(original_notes)
        spec = Spectrogram(
            audio_path="audio.ogg",
            db=np.zeros((2, 3), dtype=np.float32),
            duration=1.0,
            midi_min=60,
            midi_max=61,
            frame_times=np.linspace(0.0, 1.0, 3),
            sr=22050,
            bins_per_semitone=1,
        )

        with mock.patch.object(
            web_backend,
            "analyze_cqt",
            return_value=spec,
        ) as analyze:
            bridge.reanalyze_audio()

        analyze.assert_called_once()
        self.assertEqual(bridge.notes, original_notes)
        self.assertEqual(bridge.analysis_stats["selectedSource"], "cqt")


if __name__ == "__main__":
    unittest.main()
