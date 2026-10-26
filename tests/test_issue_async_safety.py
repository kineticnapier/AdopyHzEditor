from __future__ import annotations

import threading
import unittest
from unittest import mock

import numpy as np

import web.backend as web_backend
from core.audio_analysis import Spectrogram
from web.backend import Bridge


def _spec(path: str, duration: float, midi_min: int) -> Spectrogram:
    return Spectrogram(
        audio_path=path,
        db=np.zeros((2, 2), dtype=np.float32),
        duration=duration,
        midi_min=midi_min,
        midi_max=midi_min + 1,
        frame_times=np.array([0.0, duration], dtype=np.float64),
        sr=44100,
        bins_per_semitone=1,
        folded_to_semitone=False,
    )


class IssueAsyncSafetyTests(unittest.TestCase):
    def test_backend_bridge_initializes_without_web_ui_monkey_patch(self):
        bridge = Bridge()
        self.assertTrue(hasattr(bridge.player, "configure_preview"))
        self.assertTrue(hasattr(bridge.player, "set_speed"))

    def test_stale_analysis_cannot_overwrite_new_audio_source(self):
        bridge = Bridge()
        bridge.audio_path = "A.wav"
        bridge._source_generation = 1
        a_started = threading.Event()
        release_a = threading.Event()

        def fake_analyze(path: str, **_options):
            if path == "A.wav":
                a_started.set()
                self.assertTrue(release_a.wait(2.0))
                return _spec(path, 10.0, 12)
            return _spec(path, 20.0, 36)

        with mock.patch.object(web_backend, "analyze_cqt", side_effect=fake_analyze):
            thread_a = threading.Thread(target=bridge._analyze_current_audio)
            thread_a.start()
            self.assertTrue(a_started.wait(1.0))
            bridge._reserve_source_request()
            bridge.audio_path = "B.wav"
            thread_b = threading.Thread(target=bridge._analyze_current_audio)
            thread_b.start()
            thread_b.join(1.0)
            release_a.set()
            thread_a.join(1.0)

        self.assertIsNotNone(bridge.spectrogram)
        self.assertEqual(bridge.spectrogram.audio_path, "B.wav")
        self.assertEqual(bridge.duration, 20.0)
        self.assertEqual(bridge.midi_min, 36)
        self.assertFalse(bridge._busy)

    def test_empty_undo_and_redo_report_no_change(self):
        bridge = Bridge()
        bridge._dirty = False

        undo_result = bridge.undo()
        redo_result = bridge.redo()

        self.assertFalse(undo_result["changed"])
        self.assertFalse(redo_result["changed"])
        self.assertFalse(bridge._dirty)


if __name__ == "__main__":
    unittest.main()
