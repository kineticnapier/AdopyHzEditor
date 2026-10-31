from __future__ import annotations

import unittest

from core.note_model import Note
from exporters.adofai import build_adofai_debug_rows
from web_ui import Bridge


class AngleOnlyContinuousDebugTests(unittest.TestCase):
    @staticmethod
    def curve(*, target_angle: float | None = None) -> Note:
        return Note(
            0.0, 0.12, 69.0,
            kind="curve", midi_end=74.0,
            interpolation="linear_pitch",
            target_angle=target_angle,
        ).normalized()

    def test_fixed_note_keeps_numeric_effective_bpm(self):
        rows = build_adofai_debug_rows(
            [Note(0.0, 0.12, 69.0).normalized()],
            method="angle_only",
            angle_only_bpm=1600.0,
        )
        self.assertEqual(len(rows), 1)
        self.assertFalse(rows[0]["phase_continuous"])
        self.assertIsInstance(rows[0]["effective_bpm"], float)

    def test_continuous_curve_reports_variable_bpm_without_type_error(self):
        rows = build_adofai_debug_rows(
            [self.curve()],
            method="angle_only",
            angle_only_bpm=1600.0,
            phase_continuous_glide=True,
        )
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["phase_continuous"])
        self.assertGreater(rows[0]["tiles_est"], 0)
        self.assertEqual(rows[0]["effective_bpm"], "varies")

    def test_continuous_curve_with_final_visual_correction(self):
        rows = build_adofai_debug_rows(
            [self.curve(target_angle=90.0)],
            method="angle_only",
            angle_only_bpm=1600.0,
            phase_continuous_glide=True,
            final_angle_mode="custom",
            final_custom_angle=73.0,
        )
        self.assertEqual(rows[0]["effective_bpm"], "varies")
        self.assertTrue(rows[0]["target_angle_used"])
        self.assertTrue(rows[0]["final_visual_used"])
        self.assertAlmostEqual(rows[0]["final_angle_effective"], 73.0)
        self.assertIsInstance(rows[0]["final_bpm"], float)

    def test_bridge_preview_returns_rows_and_summary_for_continuous_curve(self):
        bridge = Bridge()
        bridge.notes = [self.curve()]
        preview = bridge.preview_adofai_debug({
            "method": "angle_only",
            "angleOnlyBpm": 1600.0,
        })
        self.assertEqual(preview["summary"]["rows"], 1)
        self.assertEqual(preview["rows"][0]["effective_bpm"], "varies")
        self.assertFalse(preview["limited"])


if __name__ == "__main__":
    unittest.main()
