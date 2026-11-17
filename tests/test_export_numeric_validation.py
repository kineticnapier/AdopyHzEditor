from __future__ import annotations

import math
import unittest
from unittest import mock

from core.note_model import Note
from web.adofai import AdoFAIMixin
from web_ui import Bridge


class ExportNumericValidationTests(unittest.TestCase):
    def make_bridge(self) -> Bridge:
        return Bridge()

    def test_nonfinite_song_offset_is_rejected_before_export(self):
        bridge = self.make_bridge()
        for invalid in (math.nan, math.inf, -math.inf, "nan", "inf"):
            with self.subTest(offset=invalid):
                with mock.patch.object(
                    AdoFAIMixin, "_prepare_adofai_export",
                    return_value=([], {"method": "rabbit_zip"}, {}),
                ):
                    with self.assertRaisesRegex(ValueError, "音源オフセット.*有限"):
                        bridge._prepare_adofai_export(
                            {
                                "songSourcePath": "song.wav",
                                "useProjectSong": True,
                                "songOffsetAuto": False,
                                "songOffsetMs": invalid,
                            },
                            None,
                        )

    def test_nonfinite_fixed_angle_is_rejected_before_note_mutation(self):
        bridge = self.make_bridge()
        for invalid in (math.nan, math.inf, -math.inf, "nan", "inf"):
            with self.subTest(angle=invalid):
                note = Note(0.0, 1.0, 60.0).normalized()
                with mock.patch.object(
                    AdoFAIMixin, "_prepare_adofai_export",
                    return_value=([note], {"method": "rabbit_zip"}, {}),
                ):
                    with self.assertRaisesRegex(ValueError, "固定角度.*有限"):
                        bridge._prepare_adofai_export(
                            {
                                "useProjectSong": False,
                                "angleCompressionMode": "fixed",
                                "angleCompressionFixedAngle": invalid,
                            },
                            None,
                        )
                self.assertIsNone(note.target_angle)

    def test_finite_export_values_keep_existing_behavior(self):
        bridge = self.make_bridge()
        note = Note(0.0, 1.0, 60.0).normalized()
        with mock.patch.object(
            AdoFAIMixin, "_prepare_adofai_export",
            return_value=([note], {"method": "rabbit_zip"}, {}),
        ):
            notes, options, workflow = bridge._prepare_adofai_export(
                {
                    "songSourcePath": "song.wav",
                    "useProjectSong": True,
                    "songOffsetAuto": False,
                    "songOffsetMs": 1250.0,
                    "angleCompressionMode": "fixed",
                    "angleCompressionFixedAngle": 165.0,
                },
                None,
            )
        self.assertEqual(options["song_offset_ms"], 1250.0)
        self.assertEqual(notes[0].target_angle, 165.0)
        self.assertEqual(workflow["songSourcePath"], "song.wav")


if __name__ == "__main__":
    unittest.main()
