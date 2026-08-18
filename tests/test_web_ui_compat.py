from __future__ import annotations

import unittest
from unittest import mock

import numpy as np

from core.audio_analysis import Spectrogram
from web_ui import Bridge


class _Window:
    def create_file_dialog(self, *args, **kwargs):
        return ["example.adopyhz"]


class WebUiCompatibilityTests(unittest.TestCase):
    def test_io_helper_contract(self):
        bridge = Bridge()
        bridge.attach_window(_Window())
        path = bridge._dialog(object(), file_types=("All files (*.*)",))
        self.assertEqual(path, "example.adopyhz")
        self.assertEqual(bridge._state_dict()["settings"]["speed"], 1.0)
        self.assertEqual(bridge._normalize_setting("volume", 150), 100)

    def test_analysis_adapter_maps_profile_and_resolution(self):
        captured = {}

        def fake_analyze(path, **kwargs):
            captured.update(kwargs)
            return Spectrogram(
                audio_path=str(path),
                db=np.zeros((4, 8), dtype=np.float32),
                duration=1.0,
                midi_min=12,
                midi_max=15,
                frame_times=np.linspace(0.0, 1.0, 8),
                sr=22050,
                bins_per_semitone=2,
                folded_to_semitone=False,
                bins_per_octave=24,
                pitch_step=0.5,
            )

        bridge = Bridge()
        bridge.audio_path = "fake.wav"
        bridge.settings["analysisProfile"] = "Normal"
        bridge.settings["cqtResolution"] = "50 cents"

        import web_ui
        with mock.patch.object(web_ui, "_core_analyze_cqt", side_effect=fake_analyze):
            bridge._analyze_current_audio()

        self.assertEqual(captured["cqt_bins_per_octave"], 24)
        self.assertFalse(captured["fold_to_semitone"])
        self.assertEqual(bridge.pitch_step, 0.5)

    def test_spectrogram_render_contract(self):
        bridge = Bridge()
        bridge.spectrogram = Spectrogram(
            audio_path="fake.wav",
            db=np.ones((2, 3), dtype=np.float32),
            duration=1.0,
            midi_min=12,
            midi_max=13,
            frame_times=np.arange(3, dtype=np.float32),
            sr=22050,
        )
        result = bridge.get_spectrogram(max_columns=64)
        self.assertTrue(result["available"])
        self.assertEqual(result["rows"], 2)
        self.assertEqual(result["cols"], 3)


if __name__ == "__main__":
    unittest.main()
