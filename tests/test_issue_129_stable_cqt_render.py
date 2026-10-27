from __future__ import annotations

import base64
import unittest
from unittest import mock

import numpy as np

import web.backend as web_backend
from core.audio_analysis import Spectrogram
from web.backend import _pool_absolute_time_columns
from web_ui import Bridge


def _decode(payload: dict) -> np.ndarray:
    raw = base64.b64decode(payload["data"])
    return np.frombuffer(raw, dtype=np.uint8).reshape(
        int(payload["rows"]),
        int(payload["cols"]),
    )


class StableCqtRenderTests(unittest.TestCase):
    def test_overlapping_viewports_reuse_one_full_song_render(self):
        columns = 20
        db = np.vstack(
            [
                np.linspace(-80.0, -10.0, columns, dtype=np.float32),
                np.array(
                    [-70, -65, -60, -55, -50, -45, -40, -35, -30, -25,
                     -20, -15, -10, -20, -30, -40, -50, -60, -70, -80],
                    dtype=np.float32,
                ),
                np.linspace(-20.0, -75.0, columns, dtype=np.float32),
            ]
        )
        bridge = Bridge()
        bridge.spectrogram = Spectrogram(
            audio_path="stable.wav",
            db=db,
            duration=19.0,
            midi_min=60,
            midi_max=62,
            frame_times=np.arange(columns, dtype=np.float64),
            sr=22_050,
        )
        bridge.duration = 19.0

        original = web_backend.enhance_spectrogram
        with mock.patch.object(
            web_backend,
            "enhance_spectrogram",
            wraps=original,
        ) as enhance:
            first = bridge.get_spectrogram(4096, 0.0, 9.0)
            second = bridge.get_spectrogram(4096, 2.0, 11.0)

        self.assertEqual(enhance.call_count, 1)
        first_pixels = _decode(first)
        second_pixels = _decode(second)
        self.assertEqual(first_pixels.shape[1], 10)
        self.assertEqual(second_pixels.shape[1], 10)
        np.testing.assert_array_equal(
            first_pixels[:, 2:10],
            second_pixels[:, 0:8],
        )

    def test_render_setting_change_invalidates_full_song_cache(self):
        bridge = Bridge()
        bridge.spectrogram = Spectrogram(
            audio_path="settings.wav",
            db=np.linspace(-80.0, -5.0, 120, dtype=np.float32).reshape(3, 40),
            duration=4.0,
            midi_min=60,
            midi_max=62,
            frame_times=np.linspace(0.0, 4.0, 40, dtype=np.float64),
            sr=22_050,
        )
        original = web_backend.enhance_spectrogram
        with mock.patch.object(
            web_backend,
            "enhance_spectrogram",
            wraps=original,
        ) as enhance:
            bridge.get_spectrogram(4096, 0.0, 2.0)
            bridge.settings["contrast"] = int(bridge.settings["contrast"]) + 1
            bridge.get_spectrogram(4096, 0.0, 2.0)

        self.assertEqual(enhance.call_count, 2)

    def test_lod_buckets_are_anchored_to_absolute_column_zero(self):
        data = np.arange(200, dtype=np.uint8).reshape(1, 200)

        first, first_left, _first_right = _pool_absolute_time_columns(
            data, 1, 101, 64
        )
        second, second_left, _second_right = _pool_absolute_time_columns(
            data, 3, 103, 64
        )

        self.assertEqual(first_left, 0)
        self.assertEqual(second_left, 2)
        self.assertLessEqual(first.shape[1], 64)
        self.assertLessEqual(second.shape[1], 64)
        np.testing.assert_array_equal(first[:, 1:], second[:, :-1])


if __name__ == "__main__":
    unittest.main()
