from __future__ import annotations

import unittest

import numpy as np

from core.audio_player import AudioPlayer, PreviewSegment


class _NoSliceList(list):
    def __getitem__(self, key):
        if isinstance(key, slice):
            raise AssertionError("audio callback must not slice the future-note list")
        return super().__getitem__(key)


class AudioPreviewSliceTests(unittest.TestCase):
    def test_mix_preview_notes_does_not_copy_future_tail(self):
        player = AudioPlayer()
        player.note_sound_enabled = True
        player.note_volume = 0.2
        player.sr = 44_100
        player.preview_notes = _NoSliceList(
            [
                PreviewSegment(0, 100, 60.0),
                PreviewSegment(10_000, 10_100, 64.0),
                PreviewSegment(20_000, 20_100, 67.0),
            ]
        )
        player._preview_ends = [100, 10_100, 20_100]

        out = np.zeros((64, 1), dtype=np.float32)
        positions = np.arange(64, dtype=np.float64)

        player._mix_preview_notes(out, positions)

        self.assertTrue(np.any(out != 0.0))


if __name__ == "__main__":
    unittest.main()
