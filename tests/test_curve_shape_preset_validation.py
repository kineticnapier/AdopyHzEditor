from __future__ import annotations

import math
import unittest
from unittest import mock

from core.note_model import Note
from web_ui import Bridge


class CurveShapePresetValidationTests(unittest.TestCase):
    def make_bridge(self) -> Bridge:
        bridge = Bridge()
        bridge.settings["curveShape"] = "ease"
        bridge.duration = 10.0
        bridge.notes = [
            Note(1.0, 2.0, 60.0, 100, "curve", 72.0, 60.0, 72.0).normalized(),
            Note(3.0, 4.0, 65.0).normalized(),
        ]
        bridge._saved_checkpoint = bridge._document_checkpoint()
        bridge._redo_stack.append(bridge._snapshot())
        return bridge

    def assert_clean(self, bridge: Bridge, original: list[Note]) -> None:
        self.assertEqual(bridge.notes, original)
        self.assertFalse(bridge._dirty)
        self.assertEqual(len(bridge._undo_stack), 0)
        self.assertEqual(len(bridge._redo_stack), 1)

    def test_invalid_curve_indices_do_not_edit_or_clear_redo(self):
        for index in (0.5, math.nan, math.inf, -math.inf, "0", True, None, -1, 99):
            with self.subTest(index=index):
                bridge = self.make_bridge()
                before = list(bridge.notes)
                with mock.patch.object(bridge, "_sync_notes_to_player") as sync:
                    result = bridge.apply_curve_shape([index])
                self.assertIs(result["changed"], False)
                self.assert_clean(bridge, before)
                sync.assert_not_called()

    def test_reapplying_same_shape_is_noop(self):
        bridge = self.make_bridge()
        before = list(bridge.notes)
        with mock.patch.object(bridge, "_sync_notes_to_player") as sync:
            result = bridge.apply_curve_shape([0, 1])
        self.assertIs(result["changed"], False)
        self.assertIs(result["dirty"], False)
        self.assert_clean(bridge, before)
        sync.assert_not_called()

    def test_shape_change_creates_one_undo_step(self):
        bridge = self.make_bridge()
        bridge.settings["curveShape"] = "linear"
        bridge._saved_checkpoint = bridge._document_checkpoint()
        before = list(bridge.notes)
        with mock.patch.object(bridge, "_sync_notes_to_player") as sync:
            result = bridge.apply_curve_shape([0, 0.5, 1])
        self.assertIs(result["changed"], True)
        self.assertTrue(bridge._dirty)
        self.assertNotEqual(bridge.notes[0], before[0])
        self.assertEqual(bridge.notes[1], before[1])
        self.assertEqual(len(bridge._undo_stack), 1)
        self.assertEqual(len(bridge._redo_stack), 0)
        sync.assert_called_once()
        with mock.patch.object(bridge, "_sync_notes_to_player"):
            bridge.undo()
        self.assertEqual(bridge.notes, before)
        self.assertFalse(bridge._dirty)

    def test_curve_shape_failure_does_not_partially_edit(self):
        bridge = self.make_bridge()
        bridge.notes.append(Note(5.0, 6.0, 62.0, 100, "curve", 74.0, 62.0, 74.0).normalized())
        bridge.settings["curveShape"] = "linear"
        bridge._saved_checkpoint = bridge._document_checkpoint()
        before = list(bridge.notes)
        calls = 0

        def fail_second(start: float, end: float):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("second curve failed")
            return start + (end - start) / 3.0, start + 2.0 * (end - start) / 3.0

        with mock.patch.object(bridge, "_curve_controls", side_effect=fail_second):
            with mock.patch.object(bridge, "_sync_notes_to_player") as sync:
                with self.assertRaisesRegex(RuntimeError, "second curve failed"):
                    bridge.apply_curve_shape([0, 2])
        self.assertEqual(calls, 2)
        self.assert_clean(bridge, before)
        sync.assert_not_called()

    def test_preset_save_rejects_noninteger_indices_before_file_io(self):
        for index in (1.5, math.nan, math.inf, -math.inf, "1", True, None, -1, 99):
            with self.subTest(index=index):
                bridge = self.make_bridge()
                before = list(bridge.notes)
                with mock.patch.object(bridge, "_load_note_preset_map") as load:
                    with mock.patch.object(bridge, "_save_note_preset_map") as save:
                        with self.assertRaisesRegex(ValueError, "1個のノートを選択"):
                            bridge.save_note_preset("Test", index)
                load.assert_not_called()
                save.assert_not_called()
                self.assert_clean(bridge, before)

    def test_preset_save_accepts_integral_float_without_editing_document(self):
        bridge = self.make_bridge()
        before = list(bridge.notes)
        with mock.patch.object(bridge, "_load_note_preset_map", return_value={}):
            with mock.patch.object(bridge, "_save_note_preset_map") as save:
                with mock.patch.object(bridge, "get_note_presets", return_value=[]):
                    result = bridge.save_note_preset("Test", 1.0)
        saved = save.call_args.args[0]["Test"]
        self.assertEqual(saved["midi"], 65.0)
        self.assertEqual(saved["start"], 0.0)
        self.assertIn("Test", result["status"])
        self.assert_clean(bridge, before)


if __name__ == "__main__":
    unittest.main()
