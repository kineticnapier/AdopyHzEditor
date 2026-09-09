from __future__ import annotations

import time
import unittest

from core.note_model import Note
from exporters.adofai import (
    AUTO_ROUTE_MIN_TWIRL_GAP,
    build_adofai_level,
    plan_auto_route_twirls,
    rebuild_angle_data_from_relatives,
)
from exporters.adofai_angles import clean_relative_angle


def _twirl_floors(actions: list[dict]) -> list[int]:
    return [
        int(action["floor"])
        for action in actions
        if action.get("eventType") == "Twirl"
    ]


def _timing_relatives(level: dict) -> list[float]:
    """Recover ADOFAI relative angles after applying Twirl semantics."""
    twirl_counts: dict[int, int] = {}
    for floor in _twirl_floors(level["actions"]):
        twirl_counts[floor] = twirl_counts.get(floor, 0) + 1

    recovered: list[float] = []
    twirled = False
    angles = level["angleData"]
    for floor in range(2, len(angles)):
        if twirl_counts.get(floor, 0) % 2:
            twirled = not twirled

        previous = float(angles[floor - 1])
        current = float(angles[floor])
        if twirled:
            relative = current - previous + 180.0
        else:
            relative = previous + 180.0 - current
        recovered.append(clean_relative_angle(relative))
    return recovered


def _without_twirls(actions: list[dict]) -> list[dict]:
    return [action for action in actions if action.get("eventType") != "Twirl"]


class AutoRouteTwirlTests(unittest.TestCase):
    def test_constant_160_sequence_folds_at_natural_extrema(self):
        relatives = [160.0] * 80

        floors, stats = plan_auto_route_twirls(relatives)
        angles = rebuild_angle_data_from_relatives(
            relatives,
            [{"floor": floor, "eventType": "Twirl"} for floor in floors],
        )

        self.assertEqual(angles[2:20], [
            20, 40, 60, 80, 100, 120, 140, 160, 180,
            160, 140, 120, 100, 80, 60, 40, 20, 0,
        ])
        self.assertGreater(len(floors), 2)
        self.assertTrue(all(b - a >= 8 for a, b in zip(floors, floors[1:])))
        self.assertEqual(stats["max_downward_run"], 0)
        self.assertLessEqual(stats["max_heading_deviation"], 90.0)

    def test_twirl_rebuild_preserves_every_timing_relative(self):
        relatives = ([160.0] * 41) + [
            142.5, 175.0, 205.25, 118.0, 159.5, 188.0, 133.25,
        ] * 35
        floors, stats = plan_auto_route_twirls(relatives)
        level = {
            "angleData": rebuild_angle_data_from_relatives(
                relatives,
                [{"floor": floor, "eventType": "Twirl"} for floor in floors],
            ),
            "actions": [
                {"floor": floor, "eventType": "Twirl"} for floor in floors
            ],
        }

        recovered = _timing_relatives(level)
        self.assertEqual(len(recovered), len(relatives))
        for expected, actual in zip(relatives, recovered):
            self.assertAlmostEqual(
                clean_relative_angle(expected),
                actual,
                places=7,
            )
        self.assertTrue(all(
            b - a >= AUTO_ROUTE_MIN_TWIRL_GAP
            for a, b in zip(floors, floors[1:])
        ))
        self.assertLessEqual(stats["max_downward_run"], 3)

    def test_export_changes_only_twirls_and_absolute_angle_representation(self):
        notes = [
            Note(1.0, 1.18, 69.0),
            Note(
                1.31,
                1.61,
                57.0,
                kind="curve",
                midi_end=72.0,
                ctrl1_midi=60.0,
                ctrl2_midi=68.0,
                interpolation="bezier_pitch",
            ),
            Note(1.75, 2.0, 64.0),
        ]
        for method in ("angle_only", "rabbit_zip"):
            with self.subTest(method=method):
                options = {
                    "method": method,
                    "angle_only_bpm": 1600.0,
                    "final_angle_mode": "scaled",
                    "phase_continuous_glide": True,
                }
                raw, _raw_stats = build_adofai_level(
                    notes,
                    visual_path_mode="raw",
                    **options,
                )
                routed, routed_stats = build_adofai_level(
                    notes,
                    visual_path_mode="auto route twirl",
                    **options,
                )

                self.assertEqual(len(raw["angleData"]), len(routed["angleData"]))
                self.assertEqual(
                    _without_twirls(raw["actions"]),
                    _without_twirls(routed["actions"]),
                )
                self.assertEqual(_timing_relatives(raw), _timing_relatives(routed))
                self.assertAlmostEqual(
                    sum(_timing_relatives(raw)),
                    sum(_timing_relatives(routed)),
                    places=7,
                )
                self.assertGreater(routed_stats["visual_route_twirls"], 0)

    def test_planning_is_deterministic_and_legacy_mode_is_an_alias(self):
        relatives = [151.0, 163.0, 177.0, 129.0, 201.0] * 50
        first = plan_auto_route_twirls(relatives)
        second = plan_auto_route_twirls(relatives)
        self.assertEqual(first, second)

        notes = [Note(0.0, 0.8, 57.0)]
        options = {
            "method": "angle_only",
            "angle_only_bpm": 1600.0,
            "final_angle_mode": "scaled",
        }
        auto, _ = build_adofai_level(
            notes,
            visual_path_mode="auto route twirl",
            **options,
        )
        legacy, _ = build_adofai_level(
            notes,
            visual_path_mode="twirl upward",
            **options,
        )
        self.assertEqual(auto["angleData"], legacy["angleData"])
        self.assertEqual(_twirl_floors(auto["actions"]), _twirl_floors(legacy["actions"]))

    def test_large_chart_planning_is_bounded(self):
        relatives = [160.0] * 100_000

        started = time.perf_counter()
        floors, stats = plan_auto_route_twirls(relatives)
        elapsed = time.perf_counter() - started

        self.assertLess(elapsed, 5.0)
        self.assertGreater(len(floors), 1_000)
        self.assertEqual(stats["max_downward_run"], 0)
        self.assertTrue(all(
            b - a >= AUTO_ROUTE_MIN_TWIRL_GAP
            for a, b in zip(floors, floors[1:])
        ))
        level = {
            "angleData": rebuild_angle_data_from_relatives(
                relatives,
                [{"floor": floor, "eventType": "Twirl"} for floor in floors],
            ),
            "actions": [
                {"floor": floor, "eventType": "Twirl"} for floor in floors
            ],
        }
        self.assertEqual(_timing_relatives(level), relatives)


if __name__ == "__main__":
    unittest.main()
