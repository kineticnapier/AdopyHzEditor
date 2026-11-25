"""An explicit final-tile setting must survive the Upward visual paths.

Upward forced every tile, including a note's fractional final tile, to the
path heading, so Horizontal / Custom final tiles silently did nothing (and
Upward avoid applied them only when it happened not to steer).  The final-tile
setting is an explicit per-note marker; the path keeps every other tile.
"""

from __future__ import annotations

import unittest

from core.note_model import Note
from exporters import adofai
from tests.test_harmony_polyrhythm_shape import _tile_seconds

# Both notes end mid-cycle, so each has a fractional final tile.
NOTES = [Note(0.0, 0.013, 69), Note(0.02, 0.0331, 72)]


def _export(method: str, path: str, final: str, **kwargs) -> dict:
    return adofai.build_adofai_level(
        NOTES, method=method, visual_path_mode=path, final_angle_mode=final, **kwargs,
    )[0]


def _headings(level: dict) -> list[float]:
    return [float(a) % 360.0 for a in level["angleData"][2:]]


class UpwardFinalAngleTests(unittest.TestCase):
    def test_upward_scaled_keeps_every_tile_on_the_path(self):
        for method in ("rabbit_zip", "angle_only"):
            with self.subTest(method=method):
                self.assertEqual(set(_headings(_export(method, "upward", "scaled"))), {90.0})

    def test_upward_honours_horizontal_final_tiles(self):
        for method in ("rabbit_zip", "angle_only"):
            for path in ("upward", "upward avoid"):
                with self.subTest(method=method, path=path):
                    headings = _headings(_export(method, path, "horizontal"))
                    sideways = [h for h in headings if h in (0.0, 180.0)]
                    self.assertEqual(len(sideways), len(NOTES))
                    if path == "upward":
                        self.assertEqual(
                            [h for h in headings if h not in (0.0, 180.0)],
                            [90.0] * (len(headings) - len(NOTES)),
                        )

    def test_upward_honours_custom_final_tiles(self):
        for method in ("rabbit_zip", "angle_only"):
            with self.subTest(method=method):
                headings = _headings(_export(method, "upward", "custom", final_custom_angle=90.0))
                # Relative 90 from an upward heading points left (180 deg).
                self.assertEqual(headings.count(180.0), len(NOTES))

    def test_final_tile_never_doubles_back_onto_the_path(self):
        for method in ("rabbit_zip", "angle_only"):
            for path in ("upward", "upward avoid"):
                with self.subTest(method=method, path=path):
                    headings = _headings(_export(method, path, "cardinal"))
                    self.assertNotIn(270.0, headings)

    def test_final_tile_override_keeps_timing(self):
        for method in ("rabbit_zip", "angle_only"):
            with self.subTest(method=method):
                plain = _tile_seconds(_export(method, "upward", "scaled"))
                marked = _tile_seconds(_export(method, "upward", "horizontal"))
                self.assertEqual(len(plain), len(marked))
                for a, b in zip(plain, marked):
                    self.assertAlmostEqual(a, b, places=12)


if __name__ == "__main__":
    unittest.main()
