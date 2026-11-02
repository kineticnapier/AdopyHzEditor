"""Viewport updates must not partially apply when a later field is invalid."""

from __future__ import annotations

import unittest

from web_ui import Bridge


class ViewAtomicUpdateTests(unittest.TestCase):
    def test_invalid_time_start_does_not_change_mode_or_window(self):
        bridge = Bridge()
        bridge.duration = 60.0
        before = dict(bridge.view)

        with self.assertRaises(ValueError):
            bridge.set_view({
                "mode": "notes",
                "windowSeconds": 5.0,
                "start": "not-a-number",
            })

        self.assertEqual(bridge.view, before)

    def test_invalid_visible_notes_does_not_change_pitch_or_time(self):
        bridge = Bridge()
        bridge.duration = 60.0
        before = dict(bridge.view)

        with self.assertRaises(ValueError):
            bridge.set_view({
                "start": 3.0,
                "pitchBottom": 32,
                "visibleNotes": "not-an-integer",
            })

        self.assertEqual(bridge.view, before)

    def test_nonfinite_time_start_rejects_without_partial_view_update(self):
        for bad in ("nan", "inf", "-inf", float("nan"), float("inf")):
            with self.subTest(value=str(bad)):
                bridge = Bridge()
                bridge.duration = 60.0
                before = dict(bridge.view)
                with self.assertRaises(ValueError):
                    bridge.set_view({
                        "mode": "notes",
                        "windowSeconds": 5.0,
                        "start": bad,
                    })
                self.assertEqual(bridge.view, before)

    def test_nonfinite_window_rejects_without_changing_view(self):
        for bad in ("nan", "inf", "-inf"):
            with self.subTest(value=bad):
                bridge = Bridge()
                bridge.duration = 60.0
                before = dict(bridge.view)
                with self.assertRaises(ValueError):
                    bridge.set_view({"mode": "notes", "windowSeconds": bad})
                self.assertEqual(bridge.view, before)

    def test_valid_combined_update_still_clamps_and_publishes(self):
        bridge = Bridge()
        bridge.duration = 60.0

        result = bridge.set_view({
            "mode": "notes",
            "windowSeconds": 20.0,
            "start": 50.0,
            "pitchBottom": 100,
            "visibleNotes": 60,
        })

        self.assertEqual(result["mode"], "notes")
        self.assertEqual(result["windowSeconds"], 20.0)
        self.assertEqual(result["start"], 40.0)
        self.assertEqual(result["visibleNotes"], 60)
        self.assertEqual(result["pitchBottom"], 68)
        self.assertEqual(bridge.view, result)


if __name__ == "__main__":
    unittest.main()
