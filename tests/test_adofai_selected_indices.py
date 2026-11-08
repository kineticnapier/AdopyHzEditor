from __future__ import annotations

import math
import unittest

from core.note_model import Note
from web_ui import Bridge


class AdoFAISelectedIndicesTests(unittest.TestCase):
    def setUp(self):
        self.bridge = Bridge()
        self.bridge.notes = [
            Note(0.0, 0.5, 60.0).normalized(),
            Note(1.0, 1.5, 72.0).normalized(),
        ]

    def test_invalid_indices_do_not_select_other_notes(self):
        for invalid in (0.5, 1.5, True, False, "1", math.nan, math.inf, -1, 999):
            with self.subTest(index=repr(invalid)):
                self.assertEqual(self.bridge._valid_export_indices([invalid]), [])

    def test_valid_indices_are_deduplicated_and_sorted(self):
        self.assertEqual(self.bridge._valid_export_indices([1, 0.0, 1.0, 0, 1]), [0, 1])

    def test_selected_only_rejects_missing_or_invalid_selection(self):
        for indices in (None, [], [0.5, False, "1"]):
            with self.subTest(indices=indices):
                with self.assertRaisesRegex(ValueError, "選択ノート"):
                    self.bridge._prepare_adofai_export(
                        {"selectedOnly": True, "useProjectSong": False}, indices
                    )

    def test_selected_only_exports_only_requested_note(self):
        notes, _, workflow = self.bridge._prepare_adofai_export(
            {"selectedOnly": True, "useProjectSong": False}, [1.0, True]
        )
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0].midi, 72.0)
        self.assertTrue(workflow["selectedOnly"])

    def test_full_export_is_unchanged_without_selected_only(self):
        notes, _, workflow = self.bridge._prepare_adofai_export(
            {"selectedOnly": False, "useProjectSong": False}, [0.5, False]
        )
        self.assertEqual(len(notes), 2)
        self.assertFalse(workflow["selectedOnly"])


if __name__ == "__main__":
    unittest.main()
