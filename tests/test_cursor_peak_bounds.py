from __future__ import annotations

import threading
from types import SimpleNamespace
import unittest

import numpy as np

from web.backend import Bridge


class CursorPeakBoundsTests(unittest.TestCase):
    def bridge(self):
        bridge = object.__new__(Bridge)
        bridge._lock = threading.RLock()
        bridge.spectrogram = SimpleNamespace(
            db=np.array([[-3.0, -4.0], [-5.0, -6.0]]),
            frame_times=np.array([0.0, 1.0]),
            duration=1.0,
            midi_min=60,
            midi_max=61,
            pitch_step=1.0,
        )
        return bridge

    def test_outside_cqt_range_keeps_cursor_pitch_without_fake_peak(self):
        bridge = self.bridge()
        for midi in (48.25, 72.25):
            with self.subTest(midi=midi):
                result = bridge.get_cursor_peak(0.25, midi)
                self.assertTrue(result["available"])
                self.assertEqual(result["cursorMidi"], midi)
                self.assertFalse(result["peakAvailable"])
                self.assertNotIn("peakMidi", result)

    def test_inside_cqt_range_keeps_peak_search(self):
        result = self.bridge().get_cursor_peak(0.25, 60.25)
        self.assertTrue(result["available"])
        self.assertTrue(result["peakAvailable"])
        self.assertEqual(result["cursorMidi"], 60.25)
        self.assertEqual(result["peakMidi"], 60.0)

    def test_nonfinite_cursor_is_unavailable(self):
        self.assertFalse(self.bridge().get_cursor_peak(0.25, float("nan"))["available"])


if __name__ == "__main__":
    unittest.main()
