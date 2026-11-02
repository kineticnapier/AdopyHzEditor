"""Settings updates must not partially mutate the document on invalid input."""

from __future__ import annotations

import unittest
from unittest import mock

from web_ui import Bridge


class SettingsAtomicUpdateTests(unittest.TestCase):
    def test_invalid_later_setting_preserves_entire_previous_batch(self):
        bridge = Bridge()
        before = bridge.get_settings()

        # Previously volume was assigned before snapDiv raised ValueError.
        with self.assertRaises(ValueError):
            bridge.update_settings({"volume": 12, "snapDiv": "not-an-integer"})

        self.assertEqual(bridge.get_settings(), before)
        self.assertFalse(bridge.get_state()["dirty"])

    def test_valid_batch_normalizes_all_known_settings(self):
        bridge = Bridge()
        result = bridge.update_settings({
            "volume": 120,
            "snapDiv": 2.7,
            "speed": 1.03,
            "unknownOption": "ignored",
        })

        self.assertEqual(result["volume"], 100)
        self.assertEqual(result["snapDiv"], 3)
        self.assertEqual(result["speed"], 1.03)
        self.assertNotIn("unknownOption", result)
        self.assertTrue(bridge.get_state()["dirty"])

    def test_nonfinite_float_setting_rejects_entire_batch(self):
        for key, bad in (("speed", "nan"), ("bpm", "inf"),
                         ("offsetMs", "-inf"), ("targetAngle", float("nan"))):
            with self.subTest(setting=key):
                bridge = Bridge()
                before = bridge.get_settings()
                with self.assertRaises(ValueError):
                    bridge.update_settings({"volume": 12, key: bad})
                self.assertEqual(bridge.get_settings(), before)
                self.assertFalse(bridge.get_state()["dirty"])

    def test_empty_and_unknown_only_batches_do_not_dirty_project(self):
        bridge = Bridge()
        before = bridge.get_settings()
        with mock.patch.object(bridge, "_apply_player_settings") as apply:
            self.assertEqual(bridge.update_settings({}), before)
            self.assertEqual(
                bridge.update_settings({"unrecognizedSetting": "ignored"}), before
            )
            apply.assert_not_called()
        self.assertFalse(bridge.get_state()["dirty"])

    def test_normalized_unchanged_values_do_not_dirty_or_reapply_audio(self):
        bridge = Bridge()
        before = bridge.get_settings()
        with mock.patch.object(bridge, "_apply_player_settings") as apply:
            self.assertEqual(
                bridge.update_settings({
                    "volume": 85.4,  # Normalizes back to the default 85.
                    "speed": 1.0,
                    "snapDiv": 1,
                }),
                before,
            )
            apply.assert_not_called()
        self.assertFalse(bridge.get_state()["dirty"])

        bridge.update_settings({"volume": 12})
        self.assertTrue(bridge.get_state()["dirty"])
        with mock.patch.object(bridge, "_apply_player_settings") as apply:
            self.assertEqual(bridge.update_settings({"volume": 12}), bridge.get_settings())
            apply.assert_not_called()

if __name__ == "__main__":
    unittest.main()
