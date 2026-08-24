from __future__ import annotations

import unittest

from core.note_model import Note
from web_ui import Bridge


class CurveRangeCutTests(unittest.TestCase):
    def _assert_fragment_matches_original(self, original: Note, fragment: Note) -> None:
        for i in range(11):
            t = fragment.start + fragment.duration * (i / 10.0)
            original_u = (t - original.start) / original.duration
            fragment_u = 0.0 if fragment.duration <= 0 else (t - fragment.start) / fragment.duration
            self.assertAlmostEqual(
                fragment.midi_at(fragment_u),
                original.midi_at(original_u),
                places=8,
            )

    def test_bezier_pitch_range_cut_preserves_both_fragments(self):
        bridge = Bridge()
        original = Note(
            1.0,
            5.0,
            60.0,
            100,
            "curve",
            72.0,
            64.0,
            69.0,
            "bezier_pitch",
            165.0,
        ).normalized()
        bridge.notes = [original]

        result = bridge.cut_notes_range([0], 2.2, 3.7)

        self.assertEqual(len(result["notes"]), 2)
        self.assertEqual(result["indices"], [0, 1])
        left, right = [Note.from_dict(row) for row in result["notes"]]
        self.assertAlmostEqual(left.start, 1.0)
        self.assertAlmostEqual(left.end, 2.2)
        self.assertAlmostEqual(right.start, 3.7)
        self.assertAlmostEqual(right.end, 5.0)
        self.assertEqual(left.target_angle, 165.0)
        self.assertEqual(right.target_angle, 165.0)
        self._assert_fragment_matches_original(original, left)
        self._assert_fragment_matches_original(original, right)

    def test_bezier_hz_range_cut_preserves_both_fragments(self):
        bridge = Bridge()
        original = Note(
            0.0,
            4.0,
            48.0,
            90,
            "curve",
            67.0,
            53.0,
            62.0,
            "bezier_hz",
        ).normalized()
        bridge.notes = [original]

        result = bridge.cut_notes_range([0], 1.25, 2.5)

        self.assertEqual(len(result["notes"]), 2)
        left, right = [Note.from_dict(row) for row in result["notes"]]
        self._assert_fragment_matches_original(original, left)
        self._assert_fragment_matches_original(original, right)

    def test_range_cut_can_remove_middle_of_fixed_note(self):
        bridge = Bridge()
        bridge.notes = [Note(0.0, 3.0, 69.0).normalized()]

        result = bridge.cut_notes_range([0], 1.0, 2.0)

        self.assertEqual([(n["start"], n["end"]) for n in result["notes"]], [(0.0, 1.0), (2.0, 3.0)])
        self.assertEqual(result["indices"], [0, 1])

    def test_range_cut_can_remove_entire_selected_note_only(self):
        bridge = Bridge()
        bridge.notes = [
            Note(0.0, 1.0, 60.0).normalized(),
            Note(0.0, 1.0, 64.0).normalized(),
        ]

        result = bridge.cut_notes_range([0], -1.0, 2.0)

        self.assertEqual(len(result["notes"]), 1)
        self.assertAlmostEqual(result["notes"][0]["midi"], 64.0)
        self.assertEqual(result["indices"], [])


if __name__ == "__main__":
    unittest.main()
