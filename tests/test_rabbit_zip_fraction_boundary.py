from __future__ import annotations

import unittest

from core.note_model import Note
from exporters.adofai import build_adofai_debug_rows
from web_ui import Bridge


class RabbitZipFractionBoundaryTests(unittest.TestCase):
    def _prepare_row(self, end: float):
        bridge = Bridge()
        bridge.notes = [Note(0.0, end, 69.0, target_angle=180.0).normalized()]
        original_end = bridge.notes[0].end

        notes, opts, _workflow = bridge._prepare_adofai_export(
            {
                "method": "rabbit_zip",
                "xMode": "floor",
                "finalAngleMode": "scaled",
            },
            None,
        )
        rows = build_adofai_debug_rows(notes, **opts)
        self.assertEqual(len(rows), 1)
        self.assertEqual(bridge.notes[0].end, original_end, "export preparation must not mutate project notes")
        return notes[0], rows[0]

    def test_a4_just_below_integer_cycle_does_not_emit_bogus_final_tile(self):
        # 440 Hz * 0.05 s = exactly 22 cycles. A tiny floating-point drift below
        # that boundary used to become both 22 whole tiles and an extra ~1-cycle
        # fractional tile because whole and frac used different floor inputs.
        prepared, row = self._prepare_row(0.05 - 5e-13)

        self.assertGreater(prepared.freq * prepared.duration, 22.0)
        self.assertLess(prepared.freq * prepared.duration - 22.0, 1e-6)
        self.assertEqual(row["whole"], 22)
        self.assertEqual(row["frac"], 0.0)
        self.assertEqual(row["tiles_est"], 22)
        self.assertEqual(row["final_angle_effective"], "")

    def test_real_fractional_cycle_is_not_snapped(self):
        # Values outside the exporter epsilon remain genuine fractional endings.
        prepared, row = self._prepare_row((22.0 - 1e-5) / 440.0)

        self.assertAlmostEqual(prepared.freq * prepared.duration, 22.0 - 1e-5, places=10)
        self.assertEqual(row["whole"], 21)
        self.assertGreater(row["frac"], 0.0)
        self.assertEqual(row["tiles_est"], 22)
        self.assertNotEqual(row["final_angle_effective"], "")


if __name__ == "__main__":
    unittest.main()
