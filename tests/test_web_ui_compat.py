from __future__ import annotations

import unittest
from unittest import mock

import numpy as np

import web.backend as web_backend
import web.io as web_io
from core.audio_analysis import Spectrogram
from core.note_model import Note
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

    def test_project_load_with_audio_syncs_preview_notes(self):
        bridge = Bridge()
        note = Note(0.25, 1.0, 69.0).normalized()

        with (
            mock.patch.object(bridge, "_dialog", return_value="project.adopyhz"),
            mock.patch.object(bridge, "_load_audio_path"),
            mock.patch.object(web_io, "load_project", return_value=("song.wav", [note], {})),
            mock.patch.object(web_io.Path, "exists", return_value=True),
        ):
            bridge.load_project_dialog()

        self.assertEqual(len(bridge.player.preview_notes), 1)
        start, end, midi = bridge.player.preview_notes[0]
        self.assertEqual(start, int(0.25 * bridge.player.sr))
        self.assertEqual(end, int(1.0 * bridge.player.sr))
        self.assertAlmostEqual(midi, 69.0)

    def test_fixed_angle_compression_keeps_fractional_mode_independent(self):
        bridge = Bridge()
        bridge.notes = [Note(0.0, 0.73, 69.0, target_angle=90.0).normalized()]

        notes, opts, _workflow = bridge._prepare_adofai_export(
            {
                "method": "rabbit_zip",
                "angleCompressionMode": "fixed",
                "angleCompressionFixedAngle": 165.0,
                "xMode": "target_bpm",
                "targetBpm": 2400.0,
                "finalAngleMode": "horizontal",
                "finalCustomAngle": 72.0,
            },
            None,
        )

        self.assertAlmostEqual(notes[0].target_angle, 165.0)
        self.assertEqual(opts["rabbit_x_mode"], "floor")
        self.assertEqual(opts["final_angle_mode"], "horizontal")
        self.assertAlmostEqual(opts["final_custom_angle"], 72.0)

    def test_curve_shape_presets_and_custom_controls(self):
        bridge = Bridge()

        bridge.settings["curveShape"] = "sine"
        self.assertEqual(bridge._curve_controls(60.0, 70.0), (61.2, 68.8))

        bridge.settings["curveShape"] = "expo_in"
        self.assertEqual(bridge._curve_controls(60.0, 70.0), (60.0, 60.5))

        bridge.settings["curveShape"] = "expo_out"
        self.assertEqual(bridge._curve_controls(60.0, 70.0), (69.5, 70.0))

        bridge.settings["curveShape"] = "custom:-50:150"
        self.assertEqual(bridge._curve_controls(60.0, 70.0), (55.0, 75.0))

    def test_apply_curve_shape_updates_existing_curve(self):
        bridge = Bridge()
        bridge.notes = [
            Note(
                0.0,
                1.0,
                60.0,
                100,
                "curve",
                72.0,
                60.0,
                72.0,
                "bezier_pitch",
            ).normalized()
        ]
        bridge.settings["curveShape"] = "custom:25:75"

        result = bridge.apply_curve_shape([0])

        self.assertIn("形状を適用", result["status"])
        self.assertAlmostEqual(bridge.notes[0].ctrl1_midi, 63.0)
        self.assertAlmostEqual(bridge.notes[0].ctrl2_midi, 69.0)

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

        with mock.patch.object(web_backend, "analyze_cqt", side_effect=fake_analyze):
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

    def test_cursor_peak_uses_strongest_nearby_bin(self):
        db = np.full((9, 3), -80.0, dtype=np.float32)
        db[5, 1] = -12.5
        bridge = Bridge()
        bridge.spectrogram = Spectrogram(
            audio_path="fake.wav",
            db=db,
            duration=1.0,
            midi_min=60,
            midi_max=64,
            frame_times=np.array([0.0, 0.5, 1.0], dtype=np.float32),
            sr=22050,
            bins_per_semitone=2,
            folded_to_semitone=False,
            bins_per_octave=24,
            pitch_step=0.5,
        )

        result = bridge.get_cursor_peak(0.5, 62.0, 2.0)
        self.assertTrue(result["available"])
        self.assertAlmostEqual(result["peakMidi"], 62.5)
        self.assertAlmostEqual(result["peakDb"], -12.5)
        self.assertEqual(result["peakName"], "D#4")
        self.assertAlmostEqual(result["peakCents"], -50.0)


if __name__ == "__main__":
    unittest.main()