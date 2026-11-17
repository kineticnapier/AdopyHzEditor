from __future__ import annotations

import unittest

from core.note_model import Note
from exporters.adofai import build_adofai_level
from web_ui import Bridge


class FixedAngleRenderedOutputTests(unittest.TestCase):
    def setUp(self):
        self.bridge = Bridge()
        self.bridge.notes = [Note(0.0, 0.073, 69.0).normalized()]

    def _options(self, angle: float) -> dict:
        return {
            "method": "rabbit_zip",
            "angleCompressionMode": "fixed",
            "angleCompressionFixedAngle": angle,
            "xMode": "floor",
            "finalAngleMode": "horizontal",
        }

    def test_fixed_angle_changes_generated_adofai_angle_data(self):
        # Verify the final exporter, not only the options prepared by Bridge.
        first_notes, first_opts, _ = self.bridge._prepare_adofai_export(
            self._options(90.0), None
        )
        second_notes, second_opts, _ = self.bridge._prepare_adofai_export(
            self._options(135.0), None
        )
        first_level, first_stats = build_adofai_level(first_notes, **first_opts)
        second_level, second_stats = build_adofai_level(second_notes, **second_opts)

        self.assertNotEqual(first_level["angleData"], second_level["angleData"])
        self.assertEqual(
            len(first_level["angleData"]), len(second_level["angleData"])
        )
        self.assertGreater(first_stats["target_angle_used"], 0)
        self.assertGreater(second_stats["target_angle_used"], 0)
        self.assertIsNone(self.bridge.notes[0].target_angle)

    def test_fixed_angle_is_reflected_in_debug_and_tile_previews(self):
        # Both preview APIs must use the same Bridge option handling as export.
        first = self._options(90.0)
        second = self._options(135.0)
        debug = self.bridge.preview_adofai_debug(second)
        self.assertTrue(debug["rows"])
        self.assertAlmostEqual(debug["rows"][0]["target_angle"], 135.0)
        self.assertTrue(debug["rows"][0]["target_angle_used"])

        first_preview = self.bridge.preview_adofai_tiles(first)
        second_preview = self.bridge.preview_adofai_tiles(second)
        self.assertTrue(first_preview["points"])
        self.assertNotEqual(first_preview["points"], second_preview["points"])
        self.assertIsNone(self.bridge.notes[0].target_angle)


if __name__ == "__main__":
    unittest.main()
