"""Warnings for stretches of an exported chart too fast to play by hand."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from core.note_model import Note
from exporters.adofai_kps import HUMAN_KPS_LIMIT, kps_report, kps_warning, tile_travel_seconds


def _straight(bpm: float, tiles: int) -> dict:
    """Straight line: every tile is a half turn, 60 / bpm seconds = bpm / 60 KPS."""
    return {"settings": {"bpm": bpm}, "angleData": [0] * tiles, "actions": []}


class TileTravelTests(unittest.TestCase):
    def test_speed_events_and_twirls(self):
        level = {
            "settings": {"bpm": 60},
            "angleData": [0, 90, 90, 90],
            "actions": [
                {"floor": 1, "eventType": "SetSpeed", "speedType": "Bpm", "beatsPerMinute": 120},
                {"floor": 2, "eventType": "SetSpeed", "speedType": "Multiplier", "bpmMultiplier": 2},
                {"floor": 2, "eventType": "Twirl"},
            ],
        }
        travel = [round(seconds, 9) for _floor, _start, seconds in tile_travel_seconds(level)]
        # 0 -> 0: half turn at 60; 0 -> 90: a 90 degree turn at 120;
        # twirled at 240: 90 -> 90 is a half turn either way.
        self.assertEqual(travel, [1.0, 0.25, 0.25, 0.25])

    def test_midspin_is_passed_instantly(self):
        level = {"settings": {"bpm": 60}, "angleData": [0, 999, 0], "actions": []}
        rows = tile_travel_seconds(level)
        self.assertEqual([floor for floor, _s, _d in rows], [0, 1])
        # After the midspin the planet comes back: 180 -> 0 is a full turn.
        self.assertAlmostEqual(rows[1][2], 2.0)


class KpsReportTests(unittest.TestCase):
    def test_playable_chart_has_no_warning(self):
        report = kps_report(_straight(HUMAN_KPS_LIMIT * 60 - 60, 50))
        self.assertEqual(report["ranges"], [])
        self.assertIsNone(kps_warning(report))

    def test_fast_stretch_is_reported_by_floor(self):
        level = _straight(6000, 40)  # 100 KPS
        level["actions"] = [
            {"floor": 10, "eventType": "SetSpeed", "speedType": "Bpm", "beatsPerMinute": 15000},  # 250 KPS
            {"floor": 20, "eventType": "SetSpeed", "speedType": "Bpm", "beatsPerMinute": 6000},
        ]
        report = kps_report(level)
        self.assertEqual(len(report["ranges"]), 1)
        stretch = report["ranges"][0]
        self.assertEqual(stretch["maxKps"], 250.0)
        self.assertLessEqual(stretch["startFloor"], 10)
        self.assertGreaterEqual(stretch["endFloor"], 19)
        self.assertIn("250", kps_warning(report))

    def test_one_sliver_tile_is_not_a_warning(self):
        # A note boundary can leave one very short tile; it is not a stretch.
        level = _straight(6000, 30)
        level["actions"] = [
            {"floor": 15, "eventType": "SetSpeed", "speedType": "Bpm", "beatsPerMinute": 600000},
            {"floor": 16, "eventType": "SetSpeed", "speedType": "Bpm", "beatsPerMinute": 6000},
        ]
        self.assertEqual(kps_report(level)["ranges"], [])

    def test_first_floor_skips_the_existing_chart(self):
        level = _straight(15000, 30)
        report = kps_report(level, first_floor=20)
        self.assertEqual(report["ranges"][0]["startFloor"], 20)


class ExportBridgeKpsTests(unittest.TestCase):
    def _export(self, midi: float):
        from web_ui import Bridge

        bridge = Bridge()
        bridge.audio_path = str(Path("analysis.wav").resolve())
        bridge.notes = [Note(1.0, 1.5, midi).normalized()]
        options = bridge.get_adofai_export_defaults()
        options.update(appendToChart=False, useProjectSong=False, copyProjectSong=False, method="rabbit_zip")
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "level.adofai"
            with mock.patch.object(bridge, "_dialog", return_value=str(out)):
                result = bridge.export_adofai_advanced(options)
            self.assertTrue(result["ok"], result)
            self.assertTrue(json.loads(out.read_text(encoding="utf-8"))["angleData"])
        return result

    def test_high_note_warns_and_low_note_does_not(self):
        high = self._export(69.0)  # 440 Hz: one tile per cycle
        self.assertTrue(high["kps"]["ranges"])
        self.assertIn("KPS", high["kpsWarning"])
        self.assertIn("KPS", high["status"])
        low = self._export(33.0)  # 55 Hz
        self.assertEqual(low["kps"]["ranges"], [])
        self.assertIsNone(low["kpsWarning"])


if __name__ == "__main__":
    unittest.main()
