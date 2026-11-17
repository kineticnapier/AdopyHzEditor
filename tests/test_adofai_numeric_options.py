from __future__ import annotations

import unittest

from web.adofai import _as_float, _as_int


class AdoFAIExportNumericOptionsTests(unittest.TestCase):
    def test_nonfinite_and_overflowing_values_fall_back_to_defaults(self):
        for value in ("inf", "-inf", "nan", 10**1000):
            with self.subTest(value=str(value)[:32]):
                self.assertEqual(_as_int(value, 17, 0, 100), 17)
                self.assertEqual(_as_float(value, 2.5, 0.0, 100.0), 2.5)

    def test_valid_numeric_options_keep_rounding_and_bounds(self):
        self.assertEqual(_as_int("12.6", 17, 0, 100), 13)
        self.assertEqual(_as_int("999", 17, 0, 100), 100)
        self.assertEqual(_as_float("12.6", 2.5, 0.0, 100.0), 12.6)
        self.assertEqual(_as_float("999", 2.5, 0.0, 100.0), 100.0)


if __name__ == "__main__":
    unittest.main()
