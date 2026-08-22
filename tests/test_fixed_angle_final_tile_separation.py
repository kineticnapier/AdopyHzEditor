from __future__ import annotations

import unittest

from core.note_model import Note
from web_ui import Bridge


class FixedAngleFinalTileSeparationTests(unittest.TestCase):
    def _prepare(self, final_mode: str, final_custom_angle: float = 90.0, x_mode: str = "floor"):
        bridge = Bridge()
        bridge.notes = [Note(0.0, 0.73, 69.0, target_angle=90.0).normalized()]
        return bridge._prepare_adofai_export(
            {
                "method": "rabbit_zip",
                "angleCompressionMode": "fixed",
                "angleCompressionFixedAngle": 165.0,
                "xMode": x_mode,
                "targetBpm": 2400.0,
                "finalAngleMode": final_mode,
                "finalCustomAngle": final_custom_angle,
            },
            None,
        )

    def test_horizontal_final_tile_is_not_overridden_by_fixed_main_angle(self):
        notes, opts, _workflow = self._prepare("horizontal")

        self.assertAlmostEqual(notes[0].target_angle, 165.0)
        self.assertEqual(opts["final_angle_mode"], "horizontal")
        self.assertAlmostEqual(opts["final_custom_angle"], 90.0)

    def test_custom_final_tile_keeps_its_own_angle(self):
        notes, opts, _workflow = self._prepare("custom", final_custom_angle=72.0)

        self.assertAlmostEqual(notes[0].target_angle, 165.0)
        self.assertEqual(opts["final_angle_mode"], "custom")
        self.assertAlmostEqual(opts["final_custom_angle"], 72.0)

    def test_fixed_main_angle_still_disables_target_bpm_x_mode(self):
        notes, opts, _workflow = self._prepare("scaled", x_mode="target_bpm")

        self.assertAlmostEqual(notes[0].target_angle, 165.0)
        self.assertEqual(opts["rabbit_x_mode"], "floor")
        self.assertEqual(opts["final_angle_mode"], "scaled")


if __name__ == "__main__":
    unittest.main()
