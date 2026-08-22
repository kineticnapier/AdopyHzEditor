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

    @staticmethod
    def _debug_row_duration(row: dict) -> float:
        """Reconstruct generated playback time from the debug row's angle/BPM data."""
        whole = int(row["whole"])
        angle = float(row["angle"])
        bpm = float(row["effective_bpm"])
        seconds = whole * (angle / 180.0) * (60.0 / bpm)

        final_angle = row.get("final_angle_effective", "")
        if final_angle != "":
            final_bpm = row.get("final_bpm", "")
            final_bpm = bpm if final_bpm == "" else float(final_bpm)
            seconds += (float(final_angle) / 180.0) * (60.0 / final_bpm)
        return seconds

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

    def test_uploaded_a2_a1_pattern_keeps_exact_total_duration(self):
        # Regression from project(1).adopyhz. At 110 BPM these durations are
        # 0.5 beat for A2 and 0.25 beat for A1. A2 is exactly 30 cycles, but the
        # stored decimal timestamps land microscopically below the integer and
        # previously emitted a bogus 31st tile, accumulating visible late drift.
        source = [
            (76.95927272727272, 77.23199999999999, 45.0),
            (77.23199999999999, 77.36836363636363, 33.0),
            (77.36836363636363, 77.50472727272727, 33.0),
            (77.50472727272727, 77.77745454545453, 45.0),
            (77.77745454545453, 77.91381818181817, 33.0),
            (77.91381818181817, 78.05018181818181, 33.0),
        ]

        bridge = Bridge()
        bridge.notes = [Note(start, end, midi).normalized() for start, end, midi in source]
        original_times = [(n.start, n.end) for n in bridge.notes]

        notes, opts, _workflow = bridge._prepare_adofai_export(
            {
                "method": "rabbit_zip",
                "xMode": "floor",
                "angleCompressionMode": "fixed",
                "angleCompressionFixedAngle": 165.0,
                "finalAngleMode": "scaled",
            },
            None,
        )
        rows = build_adofai_debug_rows(notes, **opts)

        self.assertEqual(len(rows), 6)
        self.assertEqual([(n.start, n.end) for n in bridge.notes], original_times)

        # A2 = 110 Hz * 3/11 s = 30 cycles: no fractional tile.
        for index in (0, 3):
            self.assertEqual(rows[index]["whole"], 30)
            self.assertEqual(rows[index]["frac"], 0.0)
            self.assertEqual(rows[index]["tiles_est"], 30)
            self.assertEqual(rows[index]["final_angle_effective"], "")

        # A1 = 55 Hz * 3/22 s = 7.5 cycles: the real half-cycle ending remains.
        for index in (1, 2, 4, 5):
            self.assertEqual(rows[index]["whole"], 7)
            self.assertAlmostEqual(float(rows[index]["frac"]), 0.5, places=6)
            self.assertEqual(rows[index]["tiles_est"], 8)
            self.assertAlmostEqual(float(rows[index]["final_angle_effective"]), 165.0, places=6)

        expected = source[-1][1] - source[0][0]
        generated = sum(self._debug_row_duration(row) for row in rows)
        self.assertAlmostEqual(generated, expected, places=9)


if __name__ == "__main__":
    unittest.main()
