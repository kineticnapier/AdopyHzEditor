"""Ratio-polyrhythm Harmony must keep its rhythm and draw a readable path.

The ratio-polyrhythm encodes timing purely in relative angles. These tests pin
three properties that previously failed:

* the rhythm grid is built from simple just-intonation ratios, not from
  denominator-limited approximations of equal-tempered intervals;
* the automatic cycle angle (180 degrees per tile on average) keeps the cycle
  duration while letting the pattern advance instead of piling on itself;
* any visual change to a timing angle (upward paths, angles over 360 degrees)
  is compensated with SetSpeed, so tile durations stay exact.
"""

from __future__ import annotations

import math
import unittest

from core.note_model import Note
from exporters import adofai
from tests.test_auto_route_twirl import _timing_relatives



def _tile_seconds(level: dict) -> list[float]:
    """Duration of every generated tile but the last, applying SetSpeed by floor.

    No hit follows the final tile, so its angle carries no timing.
    """
    relatives = _timing_relatives(level)[:-1]
    # Same-floor events apply in list order; sort by floor only (stable).
    speeds = sorted(
        ((int(a["floor"]), float(a["beatsPerMinute"]))
         for a in level["actions"]
         if a.get("eventType") == "SetSpeed"),
        key=lambda item: item[0],
    )
    bpm = float(level["settings"].get("bpm", 100.0))  # ADOFAI default
    out: list[float] = []
    k = 0
    for index, rel in enumerate(relatives):
        floor = index + 2
        while k < len(speeds) and speeds[k][0] <= floor:
            bpm = speeds[k][1]
            k += 1
        out.append(rel / 180.0 * 60.0 / bpm)
    return out


def _near_overlaps(level: dict, radius: float = 0.25) -> int:
    """Non-adjacent tile pairs drawn closer than radius tile lengths."""
    x = y = 0.0
    points = []
    for angle in level["angleData"]:
        x += math.cos(math.radians(float(angle)))
        y += math.sin(math.radians(float(angle)))
        points.append((x, y))
    count = 0
    for i, (px, py) in enumerate(points):
        for j in range(i - 3, -1, -1):
            qx, qy = points[j]
            if math.hypot(px - qx, py - qy) < radius:
                count += 1
    return count


def _export(chord: str, *, path: str = "raw", seconds: float = 4.0, **kwargs) -> dict:
    options = {
        "method": "harmony",
        "harmony_mode": chord,
        "harmony_timing_mode": "ratio-polyrhythm",
        "angle_only_bpm": 1000.0,
        "visual_path_mode": path,
        **kwargs,
    }
    return adofai.build_adofai_level([Note(0.0, seconds, 69)], **options)[0]


class RatioPolyrhythmJustRatioTests(unittest.TestCase):
    def _ratio_text(self, chord: str, tuning: str) -> str:
        _events, _dups, _specs, stats = adofai.build_harmony_ratio_polyrhythm_events(
            [Note(0.0, 1.0, 69)],
            harmony_mode=chord,
            harmony_custom_semitone=5.0,
            harmony_tuning=tuning,
            play_bpm=1000.0,
        )
        return str(stats["ratio_text"])

    def test_presets_use_simple_ratios_even_when_equal_temperament_is_selected(self):
        expected = {
            "major third +4": "4:5",
            "minor third +3": "5:6",
            "major triad": "4:5:6",
            "minor triad": "10:12:15",
            "dominant 7": "4:5:6:7",
            "fifth +7": "2:3",
        }
        for chord, ratio in expected.items():
            for tuning in ("equal temperament", "just intonation"):
                with self.subTest(chord=chord, tuning=tuning):
                    self.assertEqual(self._ratio_text(chord, tuning), ratio)

    def test_custom_interval_keeps_its_approximated_ratio(self):
        # A custom semitone has no just-intonation preset; 5 st -> 4/3.
        self.assertEqual(self._ratio_text("custom", "equal temperament"), "3:4")


class RatioPolyrhythmAutoCycleTests(unittest.TestCase):
    def test_auto_cycle_averages_180_degrees_and_keeps_cycle_seconds(self):
        level = _export("major triad", harmony_poly_cycle_mode="auto")
        relatives = _timing_relatives(level)
        # 4:5:6 -> 12 unique positions per cycle -> 12 * 180 = 2160 degrees.
        self.assertAlmostEqual(sum(relatives[:12]), 2160.0, places=6)
        # BPM scales by 2160/720 so one cycle still lasts 720 deg at 1000 BPM.
        self.assertAlmostEqual(float(level["settings"]["bpm"]), 3000.0, places=6)
        self.assertAlmostEqual(sum(_tile_seconds(level)[:12]), 720 * 60 / (180 * 1000), places=9)
        # Every hit stays exactly on the 4:5:6 grid.
        self.assertAlmostEqual(min(relatives[:12]), 2160.0 / 30.0, places=6)

    def test_auto_cycle_keeps_total_timing_and_removes_overlaps(self):
        fixed = _export("major triad", harmony_poly_cycle_mode="fixed")
        auto = _export("major triad", harmony_poly_cycle_mode="auto")
        self.assertEqual(len(_tile_seconds(fixed)), len(_tile_seconds(auto)))
        for a, b in zip(_tile_seconds(fixed), _tile_seconds(auto)):
            self.assertAlmostEqual(a, b, places=9)
        self.assertGreater(_near_overlaps(fixed), 50)
        self.assertEqual(_near_overlaps(auto), 0)

    def test_auto_cycle_mirrors_cycles_to_clear_folding_chords(self):
        for chord in ("minor third +3", "minor triad"):
            with self.subTest(chord=chord):
                fixed = _export(chord, harmony_poly_cycle_mode="fixed")
                auto = _export(chord, harmony_poly_cycle_mode="auto")
                self.assertTrue([a for a in auto["actions"] if a.get("eventType") == "Twirl"])
                self.assertEqual(_near_overlaps(auto), 0)
                for a, b in zip(_tile_seconds(fixed), _tile_seconds(auto)):
                    self.assertAlmostEqual(a, b, places=9)

    def test_auto_cycle_reduces_overlaps_when_the_360_cap_applies(self):
        # 4:5:6:7 has a 1/7-cycle gap; 180 deg per tile would exceed 360.
        fixed = _export("dominant 7", harmony_poly_cycle_mode="fixed")
        auto = _export("dominant 7", harmony_poly_cycle_mode="auto")
        self.assertLess(_near_overlaps(auto), _near_overlaps(fixed) / 5)
        self.assertLessEqual(max(_timing_relatives(auto)[:-1]), 360.0)
        self.assertFalse([a for a in auto["actions"] if a.get("eventType") == "SetSpeed"])

    def test_auto_cycle_leaves_twirl_routing_to_the_path_planner(self):
        level = _export("minor triad", path="auto route twirl", harmony_poly_cycle_mode="auto")
        fixed = _export("minor triad", path="auto route twirl", harmony_poly_cycle_mode="fixed")
        for a, b in zip(_tile_seconds(fixed), _tile_seconds(level)):
            self.assertAlmostEqual(a, b, places=9)

    def test_fixed_cycle_is_default_for_direct_exporter_calls(self):
        level = _export("major triad")
        self.assertAlmostEqual(float(level["settings"]["bpm"]), 1000.0, places=6)
        self.assertAlmostEqual(sum(_timing_relatives(level)[:12]), 720.0, places=6)


class RatioPolyrhythmTimingPreservationTests(unittest.TestCase):
    def test_upward_paths_preserve_ratio_timing(self):
        raw = _tile_seconds(_export("major triad", path="raw"))
        for path in ("upward", "upward avoid", "twirl upward"):
            with self.subTest(path=path):
                shaped = _tile_seconds(_export("major triad", path=path))
                self.assertEqual(len(shaped), len(raw))
                for a, b in zip(raw, shaped):
                    self.assertAlmostEqual(a, b, places=9)

    def test_raw_path_needs_no_setspeed(self):
        level = _export("major triad", path="raw", harmony_poly_cycle_mode="auto")
        self.assertFalse([a for a in level["actions"] if a.get("eventType") == "SetSpeed"])

    def test_gaps_longer_than_360_degrees_keep_their_duration(self):
        # Octave-folded octave is a single hit per 720-degree cycle.
        level = _export("octave +12", seconds=1.0, harmony_poly_cycle_mode="fixed")
        seconds = _tile_seconds(level)
        cycle = 720 * 60 / (180 * 1000)
        self.assertGreater(len(seconds), 2)
        for value in seconds:
            self.assertAlmostEqual(value, cycle, places=9)
        self.assertAlmostEqual(sum(seconds), (math.ceil(1.0 / cycle) - 1) * cycle, places=9)


class RatioPolyrhythmWebOptionTests(unittest.TestCase):
    def _bridge(self):
        from web_ui import Bridge

        bridge = Bridge()
        bridge.notes = [Note(0.0, 1.0, 69.0).normalized()]
        return bridge

    def test_dialog_defaults_to_auto_cycle_angle(self):
        self.assertEqual(self._bridge().get_adofai_export_defaults()["harmonyPolyCycleMode"], "auto")

    def test_cycle_mode_reaches_the_exporter(self):
        bridge = self._bridge()
        base = {"method": "harmony", "harmonyTimingMode": "ratio-polyrhythm", "useProjectSong": False}
        _notes, opts, _workflow = bridge._prepare_adofai_export(base, None)
        self.assertEqual(opts["harmony_poly_cycle_mode"], "auto")
        _notes, opts, _workflow = bridge._prepare_adofai_export(
            {**base, "harmonyPolyCycleMode": "fixed"}, None,
        )
        self.assertEqual(opts["harmony_poly_cycle_mode"], "fixed")
        _notes, opts, _workflow = bridge._prepare_adofai_export(
            {**base, "harmonyPolyCycleMode": "bogus"}, None,
        )
        self.assertEqual(opts["harmony_poly_cycle_mode"], "auto")


if __name__ == "__main__":
    unittest.main()
