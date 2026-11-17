from __future__ import annotations

import unittest

from web_ui import Bridge


class CustomCurveShapeNumericValidationTests(unittest.TestCase):
    def test_nonfinite_custom_controls_fall_back_to_linear_endpoints(self):
        bridge = Bridge()
        for shape in (
            "custom:nan:50",
            "custom:50:inf",
            "custom:-inf:50",
            "custom:NaN:Infinity",
            "custom:1e309:75",
        ):
            with self.subTest(shape=shape):
                bridge.settings["curveShape"] = shape
                self.assertEqual(bridge._curve_controls(60.0, 70.0), (60.0, 70.0))

    def test_finite_custom_controls_preserve_range_clamping(self):
        bridge = Bridge()
        bridge.settings["curveShape"] = "custom:-250:350"
        self.assertEqual(bridge._curve_controls(60.0, 70.0), (40.0, 90.0))
        bridge.settings["curveShape"] = "custom:25:75"
        self.assertEqual(bridge._curve_controls(60.0, 70.0), (62.5, 67.5))


if __name__ == "__main__":
    unittest.main()
