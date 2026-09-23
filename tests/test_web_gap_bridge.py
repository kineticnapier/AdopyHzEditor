from __future__ import annotations

import unittest

from core.note_model import Note
from exporters.adofai import build_adofai_level as core_build_adofai_level
import web.adofai as web_adofai


class WebGapBridgeTests(unittest.TestCase):
    def _notes(self) -> list[Note]:
        return [
            Note(0.0, 0.1, 69.0),
            Note(0.5, 0.6, 69.0),
        ]

    def _pause(self, level: dict) -> dict:
        pauses = [a for a in level["actions"] if a.get("eventType") == "Pause"]
        self.assertEqual(len(pauses), 1)
        return pauses[0]

    def test_angle_only_gap_becomes_one_180_degree_bridge_tile(self):
        core_level, core_stats = core_build_adofai_level(
            self._notes(),
            method="angle_only",
            angle_only_bpm=1200.0,
            visual_path_mode="raw",
        )
        pause = self._pause(core_level)
        pause_floor = int(pause["floor"])

        level, stats = web_adofai.build_adofai_level(
            self._notes(),
            method="angle_only",
            angle_only_bpm=1200.0,
            visual_path_mode="raw",
        )

        self.assertFalse(any(a.get("eventType") == "Pause" for a in level["actions"]))
        self.assertEqual(len(level["angleData"]), len(core_level["angleData"]) + 1)
        self.assertEqual(stats["gap_bridge_tiles"], 1)
        self.assertAlmostEqual(stats["gap_bridge_seconds"], 0.4, places=6)
        self.assertEqual(stats["tiles_total"], core_stats["tiles_total"] + 1)

        # Duplicate absolute heading means an exact 180-degree relative tile.
        self.assertAlmostEqual(
            float(level["angleData"][pause_floor]),
            float(level["angleData"][pause_floor + 1]),
            places=7,
        )

        bridge_speed = [
            a for a in level["actions"]
            if a.get("eventType") == "SetSpeed" and int(a.get("floor", -1)) == pause_floor + 1
        ]
        self.assertEqual(len(bridge_speed), 1)
        self.assertAlmostEqual(float(bridge_speed[0]["beatsPerMinute"]), 150.0, places=6)

        # Angle-only has no per-note SetSpeed, so the wrapper must restore the
        # global BPM on the next original tile.
        restore = [
            a for a in level["actions"]
            if a.get("eventType") == "SetSpeed" and int(a.get("floor", -1)) == pause_floor + 2
        ]
        self.assertTrue(any(abs(float(a["beatsPerMinute"]) - 1200.0) < 1e-6 for a in restore))

    def test_angle_compression_next_note_speed_shifts_after_bridge(self):
        core_level, _ = core_build_adofai_level(
            self._notes(),
            method="rabbit_zip",
            visual_path_mode="raw",
        )
        pause = self._pause(core_level)
        pause_floor = int(pause["floor"])
        next_original_speeds = [
            a for a in core_level["actions"]
            if a.get("eventType") == "SetSpeed" and int(a.get("floor", -1)) == pause_floor + 1
        ]
        self.assertTrue(next_original_speeds)

        level, stats = web_adofai.build_adofai_level(
            self._notes(),
            method="rabbit_zip",
            visual_path_mode="raw",
        )

        self.assertEqual(stats["gap_bridge_tiles"], 1)
        self.assertFalse(any(a.get("eventType") == "Pause" for a in level["actions"]))

        bridge_speed = [
            a for a in level["actions"]
            if a.get("eventType") == "SetSpeed" and int(a.get("floor", -1)) == pause_floor + 1
        ]
        self.assertEqual(len(bridge_speed), 1)
        self.assertAlmostEqual(float(bridge_speed[0]["beatsPerMinute"]), 150.0, places=6)

        shifted_next_speeds = [
            a for a in level["actions"]
            if a.get("eventType") == "SetSpeed" and int(a.get("floor", -1)) == pause_floor + 2
        ]
        self.assertTrue(shifted_next_speeds)
        expected = float(next_original_speeds[0]["beatsPerMinute"])
        self.assertTrue(any(abs(float(a["beatsPerMinute"]) - expected) < 1e-6 for a in shifted_next_speeds))

    def test_harmony_keeps_existing_pause_strategy(self):
        level, stats = web_adofai.build_adofai_level(
            self._notes(),
            method="harmony",
            angle_only_bpm=1200.0,
            harmony_mode="off",
            harmony_timing_mode="angle-only",
        )
        self.assertNotIn("gap_bridge_tiles", stats)
        self.assertTrue(any(a.get("eventType") == "Pause" for a in level["actions"]))


if __name__ == "__main__":
    unittest.main()
