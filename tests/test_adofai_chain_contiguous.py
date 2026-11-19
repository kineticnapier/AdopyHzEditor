from __future__ import annotations

import unittest

from core.note_model import Note
from exporters.adofai import (
    ChainedNote,
    build_adofai_debug_rows,
    build_adofai_level,
    chain_contiguous_notes,
    curve_phase_dt_intervals,
)
from web_ui import Bridge

A4 = 440.0  # MIDI 69
A5 = 880.0  # MIDI 81


def _fixed(start: float, cycles: float, midi: float = 69.0, freq: float = A4) -> Note:
    return Note(start, start + cycles / freq, midi)


class ChainContiguousNotesTests(unittest.TestCase):
    def test_back_to_back_notes_merge_and_gaps_split(self):
        a = _fixed(0.0, 2.25)
        b = _fixed(a.end, 2.25)
        c = _fixed(b.end + 0.01, 1.0)  # 10 ms gap starts a new run
        out = chain_contiguous_notes([a, b, c])
        self.assertEqual(len(out), 2)
        self.assertIsInstance(out[0], ChainedNote)
        self.assertEqual(len(out[0].segments), 2)
        self.assertAlmostEqual(out[0].start, a.start)
        self.assertAlmostEqual(out[0].end, b.end)
        self.assertNotIsInstance(out[1], ChainedNote)

    def test_different_target_angles_do_not_merge(self):
        a = _fixed(0.0, 2.0).with_target_angle(90.0)
        b = _fixed(a.end, 2.0)
        self.assertEqual(len(chain_contiguous_notes([a, b])), 2)

    def test_phase_carries_across_a_pitch_jump(self):
        a = _fixed(0.0, 2.25, 69.0, A4)
        b = _fixed(a.end, 2.5, 81.0, A5)
        (chain,) = chain_contiguous_notes([a, b])
        intervals, total = curve_phase_dt_intervals(chain)
        self.assertAlmostEqual(total, 4.75, places=6)
        self.assertAlmostEqual(sum(intervals), chain.duration, places=9)
        self.assertEqual(len(intervals), 5)  # 4 whole cycles + one partial at the very end
        self.assertAlmostEqual(intervals[0], 1 / A4, places=7)
        # The third cycle straddles the boundary: 0.25 cycle at 440 Hz, then 0.75 at 880 Hz.
        self.assertAlmostEqual(intervals[2], 0.25 / A4 + 0.75 / A5, places=7)
        self.assertAlmostEqual(intervals[3], 1 / A5, places=7)

    def test_chain_keeps_curve_segments(self):
        beat = 60 / 210
        notes = [
            Note(0.0, 0.068, 29.0),
            Note(0.068, 0.110, 54.0, kind="curve", midi_end=29.0, ctrl1_midi=36.0, ctrl2_midi=30.0),
            Note(0.110, beat, 29.0),
        ]
        (chain,) = chain_contiguous_notes(notes)
        self.assertAlmostEqual(chain.midi_at(0.0), 29.0)
        self.assertAlmostEqual(chain.midi_at(0.069 / beat), notes[1].midi_at(0.001 / 0.042), places=6)
        self.assertEqual(chain.pitch_bounds, (29.0, 54.0))


class ChainContiguousExportTests(unittest.TestCase):
    def setUp(self):
        a = _fixed(0.0, 2.25)
        self.notes = [a, _fixed(a.end, 2.25)]

    def test_chained_export_drops_the_boundary_partial_tile(self):
        for method in ("rabbit_zip", "angle_only", "direct_180"):
            with self.subTest(method=method):
                _, split = build_adofai_level(self.notes, method=method)
                _, chained = build_adofai_level(self.notes, method=method, chain_contiguous=True)
                self.assertEqual(split["tiles_total"], 6)  # 3 + 3, each with a partial tile
                self.assertEqual(chained["tiles_total"], 5)  # 4.5 cycles as one run
                self.assertEqual(chained["chained_runs"], 1)
                self.assertEqual(chained["notes_merged_by_chain"], 1)

    def test_option_defaults_off_in_exporter(self):
        _, stats = build_adofai_level(self.notes)
        self.assertFalse(stats["chain_contiguous"])
        self.assertEqual(stats["chained_runs"], 0)

    def test_debug_rows_follow_the_chain(self):
        rows = build_adofai_debug_rows(self.notes, chain_contiguous=True)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["chained_notes"], 2)

    def test_harmony_ignores_chaining(self):
        _, split = build_adofai_level(self.notes, method="harmony", harmony_mode="off")
        _, chained = build_adofai_level(self.notes, method="harmony", harmony_mode="off", chain_contiguous=True)
        self.assertEqual(split["tiles_total"], chained["tiles_total"])


class ChainContiguousBridgeOptionTests(unittest.TestCase):
    def setUp(self):
        self.bridge = Bridge()
        self.bridge.notes = [Note(0.0, 0.5, 60.0).normalized(), Note(0.5, 1.0, 62.0).normalized()]

    def test_web_export_chains_by_default(self):
        self.assertTrue(self.bridge.get_adofai_export_defaults()["chainContiguous"])
        _, options, _ = self.bridge._prepare_adofai_export({}, None)
        self.assertTrue(options["chain_contiguous"])

    def test_web_export_can_turn_chaining_off(self):
        _, options, _ = self.bridge._prepare_adofai_export({"chainContiguous": False}, None)
        self.assertFalse(options["chain_contiguous"])


if __name__ == "__main__":
    unittest.main()
