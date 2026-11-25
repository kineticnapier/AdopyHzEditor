"""Appending a generated Hz chart to an existing ADOFAI level."""

from __future__ import annotations

import json
import unittest

from core.note_model import Note
from exporters.adofai_append import AppendError, append_level, load_adofai_text
from web.gap_bridge import build_adofai_level_with_gap_bridges as build_level


def _travel_seconds(level: dict, first_floor: int = 0) -> list[float]:
    """Seconds of each travel floor -> floor+1, from ``first_floor`` on.

    Plain ADOFAI timing: clockwise turn of 180 - (next - prev) degrees,
    mirrored while twirled; SetSpeed (Bpm) applies from its floor on.
    """
    angles = [0.0] + [float(a) for a in level["angleData"]]
    bpm = float(level.get("settings", {}).get("bpm", 100.0))
    twirled = False
    speeds: dict[int, float] = {}
    twirls: dict[int, int] = {}
    for action in level.get("actions", []):
        floor = int(action["floor"])
        if action["eventType"] == "SetSpeed":
            speeds[floor] = float(action["beatsPerMinute"])
        elif action["eventType"] == "Twirl":
            twirls[floor] = twirls.get(floor, 0) + 1
    out = []
    for floor in range(len(angles) - 1):
        if floor in speeds:
            bpm = speeds[floor]
        if twirls.get(floor, 0) % 2:
            twirled = not twirled
        turn = (angles[floor] + 180.0 - angles[floor + 1]) % 360.0
        if twirled:
            turn = (360.0 - turn) % 360.0
        if turn <= 1e-9:
            turn = 360.0
        if floor >= first_floor:
            out.append(turn / 180.0 * 60.0 / bpm)
    return out


def _base_level(*, twirls: int = 0) -> dict:
    actions = [{"floor": 2, "eventType": "SetSpeed", "speedType": "Bpm", "beatsPerMinute": 180, "bpmMultiplier": 1}]
    actions += [{"floor": 3 + i, "eventType": "Twirl"} for i in range(twirls)]
    actions.append({"floor": 5, "eventType": "SetSpeed", "speedType": "Multiplier", "beatsPerMinute": 100, "bpmMultiplier": 2})
    return {
        "settings": {"version": 15, "bpm": 140, "songFilename": "song.ogg", "offset": 1234, "artist": "Someone"},
        "angleData": [0, 90, 45, 180, 270, 300, 15],
        "actions": actions,
        "decorations": [],
    }


def _generated(method: str) -> dict:
    notes = [Note(1.0, 1.2, 69.0), Note(1.3, 1.5, 72.0), Note(1.6, 1.8, 64.5)]
    level, _stats = build_level(notes, method=method)
    return level


class AppendLevelTests(unittest.TestCase):
    def assert_same_timing(self, merged: dict, generated: dict, joint: int):
        tail = _travel_seconds(merged, joint)
        expected = _travel_seconds(generated)
        self.assertEqual(len(tail), len(expected))
        for got, want in zip(tail, expected):
            self.assertAlmostEqual(got, want, places=9)

    def test_appended_part_keeps_every_travel_time(self):
        for method in ("rabbit_zip", "angle_only"):
            for twirls in (0, 1, 2):
                with self.subTest(method=method, twirls=twirls):
                    base = _base_level(twirls=twirls)
                    generated = _generated(method)
                    merged, info = append_level(base, generated)
                    self.assertEqual(info["jointFloor"], len(base["angleData"]))
                    self.assertEqual(len(merged["angleData"]), len(base["angleData"]) + len(generated["angleData"]))
                    self.assert_same_timing(merged, generated, info["jointFloor"])

    def test_existing_level_is_left_as_it_was(self):
        base = _base_level(twirls=1)
        before = json.loads(json.dumps(base))
        merged, info = append_level(base, _generated("rabbit_zip"))
        self.assertEqual(base, before)  # input untouched
        self.assertEqual(merged["settings"], base["settings"])
        joint = info["jointFloor"]
        self.assertEqual(merged["angleData"][:joint], base["angleData"])
        self.assertEqual(
            _travel_seconds(merged)[: joint - 1],
            _travel_seconds(base)[: joint - 1],
        )
        self.assertEqual(
            [a for a in merged["actions"] if a["floor"] < joint],
            [a for a in base["actions"] if a["floor"] < joint],
        )

    def test_empty_level_and_midspin_ending(self):
        generated = _generated("angle_only")
        merged, info = append_level({"settings": {}, "angleData": [], "actions": []}, generated)
        self.assertEqual(info["jointFloor"], 0)
        self.assert_same_timing(merged, generated, 0)
        midspin = {"settings": {}, "angleData": [0, 90, 999], "actions": []}
        merged, info = append_level(midspin, generated)
        self.assertAlmostEqual(info["rotation"], 270.0)

    def test_old_path_data_levels_are_refused(self):
        with self.assertRaises(AppendError):
            append_level({"settings": {}, "pathData": "RRRR", "actions": []}, _generated("angle_only"))


class LoadAdofaiTextTests(unittest.TestCase):
    def test_trailing_commas_and_bom_are_accepted(self):
        text = '﻿{"settings": {"levelDesc": "a, ] b,}", "bpm": 120, }, "angleData": [0, 90, ], "actions": [ ], }'
        data = load_adofai_text(text)
        self.assertEqual(data["angleData"], [0, 90])
        self.assertEqual(data["settings"]["levelDesc"], "a, ] b,}")

    def test_garbage_is_reported(self):
        with self.assertRaises(AppendError):
            load_adofai_text("not a level")



class AppendExportBridgeTests(unittest.TestCase):
    def _bridge(self):
        from pathlib import Path

        from web_ui import Bridge

        bridge = Bridge()
        bridge.audio_path = str(Path("analysis.wav").resolve())
        bridge.notes = [Note(1.0, 1.2, 69.0).normalized(), Note(1.3, 1.5, 72.0).normalized()]
        return bridge

    def test_export_appends_in_place_and_keeps_a_backup(self):
        import tempfile
        from pathlib import Path
        from unittest import mock

        bridge = self._bridge()
        with tempfile.TemporaryDirectory() as tmp:
            chart = Path(tmp) / "my level.adofai"
            original = '﻿{"settings": {"songFilename": "song.ogg", "offset": 500, "bpm": 150, }, "angleData": [0, 90, 180, ], "actions": [], "decorations": []}'
            chart.write_bytes(original.encode("utf-8"))
            options = bridge.get_adofai_export_defaults()
            self.assertTrue(options["appendToChart"])  # append is the default
            options.update(appendToChart=True, useProjectSong=True)
            with mock.patch.object(bridge, "_dialog", return_value=str(chart)) as dialog:
                result = bridge.export_adofai_advanced(options)
            self.assertTrue(result["ok"], result)
            self.assertEqual(dialog.call_args.args[0], __import__("webview").FileDialog.OPEN)
            merged = json.loads(chart.read_text(encoding="utf-8"))
            self.assertEqual(merged["settings"], {"songFilename": "song.ogg", "offset": 500, "bpm": 150})
            self.assertEqual(merged["angleData"][:3], [0, 90, 180])
            self.assertEqual(len(merged["angleData"]), 3 + result["stats"]["tiles_total"])
            backup = Path(result["backupPath"])
            self.assertEqual(backup.name, "my level.adofai.bak")
            self.assertEqual(backup.read_bytes(), original.encode("utf-8"))

    def test_broken_chart_is_reported_and_left_alone(self):
        import tempfile
        from pathlib import Path
        from unittest import mock

        bridge = self._bridge()
        with tempfile.TemporaryDirectory() as tmp:
            chart = Path(tmp) / "old.adofai"
            chart.write_text('{"settings": {}, "pathData": "RRRR", "actions": []}', encoding="utf-8")
            options = bridge.get_adofai_export_defaults()
            options.update(appendToChart=True)
            with mock.patch.object(bridge, "_dialog", return_value=str(chart)):
                result = bridge.export_adofai_advanced(options)
            self.assertFalse(result["ok"])
            self.assertIn("pathData", result["status"])
            self.assertFalse((Path(tmp) / "old.adofai.bak").exists())
            self.assertIn("RRRR", chart.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
