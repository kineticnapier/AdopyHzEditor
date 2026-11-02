"""Settings updates must not partially mutate the document on invalid input."""

from __future__ import annotations

import unittest

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


if __name__ == "__main__":
    unittest.main()
