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

    def test_full_export_defaults_use_all_notes_even_with_selection(self):
        # The default dialog opens with selectedOnly=False. Selecting a later
        # note must not shift the displayed manual song offset for full export.
        defaults = self.bridge.get_adofai_export_defaults([1])
        self.assertFalse(defaults["selectedOnly"])
        self.assertEqual(defaults["songOffsetMs"], 0.0)

    def test_selected_only_defaults_use_selected_notes(self):
        defaults = self.bridge.get_adofai_export_defaults([1], selected_only=True)
        self.assertTrue(defaults["selectedOnly"])
        self.assertEqual(defaults["songOffsetMs"], 1000.0)

    def test_defaults_include_both_offsets_for_scope_switches(self):
        full = self.bridge.get_adofai_export_defaults([1])
        selected = self.bridge.get_adofai_export_defaults([1], selected_only=True)
        for defaults in (full, selected):
            self.assertEqual(defaults["fullSongOffsetMs"], 0.0)
            self.assertEqual(defaults["selectedSongOffsetMs"], 1000.0)
        self.assertEqual(full["songOffsetMs"], full["fullSongOffsetMs"])
        self.assertEqual(selected["songOffsetMs"], selected["selectedSongOffsetMs"])

    def test_selected_only_auto_offset_still_uses_selected_note(self):
        # Switching to selected-only mode must keep its existing automatic
        # offset semantics, independent of the full-export dialog defaults.
        self.bridge.audio_path = "test-song.wav"
        _, options, _ = self.bridge._prepare_adofai_export(
            {"selectedOnly": True, "songOffsetAuto": True, "useProjectSong": True},
            [1],
        )
        self.assertEqual(options["song_offset_ms"], 1000.0)

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
