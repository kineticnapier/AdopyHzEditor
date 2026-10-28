from __future__ import annotations

import math
import unittest
from unittest import mock

import numpy as np

from core.audio_player import AudioPlayer
from core.note_model import Note


class PlaybackSpeedSyncTests(unittest.TestCase):
    def _player(self) -> AudioPlayer:
        player = AudioPlayer()
        player.sr = 1000
        return player

    def test_source_positions_cover_1x_half_and_double_speed(self):
        player = self._player()
        for speed in (1.0, 0.5, 2.0):
            with self.subTest(speed=speed):
                positions = player._source_positions(250.0, 5, speed)
                np.testing.assert_allclose(
                    positions,
                    250.0 + np.arange(5) * speed,
                )

    def test_note_preview_starts_at_same_source_time_for_each_speed(self):
        player = self._player()
        player.note_sound_enabled = True
        player.note_volume = 1.0
        player.note_instrument = "organ"
        player.preview_notes = [(1000, 1100, 69.0)]
        block_start = 950.0

        for speed in (1.0, 0.5, 2.0):
            with self.subTest(speed=speed):
                positions = player._source_positions(block_start, 400, speed)
                output = np.zeros((len(positions), 1), dtype=np.float32)
                player._mix_preview_notes(output, positions)
                onset = int(math.ceil((1000.0 - block_start) / speed))

                self.assertTrue(np.allclose(output[:onset], 0.0))
                self.assertGreater(np.max(np.abs(output[onset:onset + 20])), 0.0)

    def test_metronome_starts_at_same_source_time_for_each_speed(self):
        player = self._player()
        player.metronome_enabled = True
        player.metronome_bpm = 60.0
        player.metronome_offset_sec = 0.0
        player.metronome_volume = 1.0
        block_start = 950.0

        with mock.patch.object(player, "_click_wave", return_value=np.ones((20, 1), dtype=np.float32)):
            for speed in (1.0, 0.5, 2.0):
                with self.subTest(speed=speed):
                    positions = player._source_positions(block_start, 400, speed)
                    output = np.zeros((len(positions), 1), dtype=np.float32)
                    player._mix_metronome(output, positions)
                    onset = int(math.ceil((1000.0 - block_start) / speed))

                    self.assertTrue(np.allclose(output[:onset], 0.0))
                    self.assertGreater(output[onset, 0], 0.0)

    def test_nonzero_seek_uses_seeked_source_timeline(self):
        player = self._player()
        player.virtual_duration_samples = 10000
        player.seek(2.75)
        player.set_playback_speed(2.0)

        positions = player._source_positions(player._pos_float, 4, player.playback_speed)

        np.testing.assert_allclose(positions, [2750.0, 2752.0, 2754.0, 2756.0])

    def test_callback_passes_one_shared_source_timeline_to_both_mixers(self):
        player = self._player()
        player.audio = np.zeros((10000, 1), dtype=np.float32)
        player.playing = True
        player._pos_float = 2750.0
        player.pos = 2750
        player.playback_speed = 2.0
        output = np.zeros((4, 1), dtype=np.float32)

        with (
            mock.patch.object(player, "_mix_preview_notes") as preview,
            mock.patch.object(player, "_mix_metronome") as metronome,
        ):
            player._callback(output, 4, None, None)

        preview_positions = preview.call_args.args[1]
        metronome_positions = metronome.call_args.args[1]
        np.testing.assert_allclose(preview_positions, [2750.0, 2752.0, 2754.0, 2756.0])
        np.testing.assert_array_equal(preview_positions, metronome_positions)

    def test_speed_change_preserves_fractional_source_position(self):
        player = self._player()
        player.pos = 123
        player._pos_float = 123.75

        player.set_playback_speed(4.0)

        self.assertEqual(player.pos, 123)
        self.assertEqual(player._pos_float, 123.75)

    def test_curve_preview_phase_stays_continuous_after_octave_shift(self):
        player = self._player()
        player.note_sound_enabled = True
        player.note_volume = 1.0
        player.note_instrument = "sine"
        player.set_preview_notes([
            Note(0.0, 0.12, 69.0, kind="curve", midi_end=72.0,
                 ctrl1_midi=69.0, ctrl2_midi=72.0),
        ])
        self.assertGreater(len(player.preview_notes), 2)
        segment = player.preview_notes[1]

        for octave_shift in (0, 1, -1):
            with self.subTest(octave_shift=octave_shift):
                player.note_octave_shift = octave_shift
                output = np.zeros((1, 1), dtype=np.float32)
                player._mix_preview_notes(
                    output,
                    np.array([float(segment.start)], dtype=np.float64),
                )
                expected_phase = segment.phase * (2.0 ** octave_shift)
                expected = math.sin(expected_phase) * player.note_volume
                self.assertAlmostEqual(float(output[0, 0]), expected, places=5)


if __name__ == "__main__":
    unittest.main()
