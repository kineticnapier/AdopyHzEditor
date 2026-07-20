from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from quick_hz_tools import (
    AppendGeneratedDataToChart,
    CalculateHzInfo,
    HzToolError,
    ReadChartTailFloor,
    SaveChartAs,
    default_added_path,
)


class QuickHzToolsTests(unittest.TestCase):
    def write_chart(self, directory: str, name: str, data: dict) -> Path:
        path = Path(directory) / name
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def test_rejects_interval_longer_than_one_tile(self) -> None:
        with self.assertRaises(HzToolError):
            CalculateHzInfo(180.0, 1.0)

    def test_rejects_legacy_path_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_chart(tmp, "legacy.adofai", {"pathData": "R5", "actions": []})
            with self.assertRaisesRegex(HzToolError, "pathData"):
                ReadChartTailFloor(path)

    def test_append_respects_active_twirl(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_chart(
                tmp,
                "twirl.adofai",
                {
                    "angleData": [0],
                    "actions": [{"floor": 0, "eventType": "Twirl"}],
                },
            )
            info = CalculateHzInfo(120.0, 4.0)
            data, result = AppendGeneratedDataToChart(path, info, 1, add_set_speed=False)

            self.assertEqual(result.start_floor, 0)
            self.assertEqual(data["angleData"], [0, 270])

    def test_append_requires_tail_floor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_chart(tmp, "level.adofai", {"angleData": [0, 90], "actions": []})
            info = CalculateHzInfo(120.0, 4.0)
            with self.assertRaisesRegex(HzToolError, "tail floor"):
                AppendGeneratedDataToChart(path, info, 1, start_floor=0)

    def test_default_added_path_does_not_reuse_existing_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = self.write_chart(tmp, "level.adofai", {"angleData": [0]})
            self.write_chart(tmp, "level_added.adofai", {"angleData": [90]})
            self.assertEqual(default_added_path(source).name, "level_added_2.adofai")

    def test_explicit_existing_output_requires_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = self.write_chart(tmp, "level.adofai", {"angleData": [0]})
            output = self.write_chart(tmp, "output.adofai", {"angleData": [90]})
            with self.assertRaisesRegex(HzToolError, "Overwrite"):
                SaveChartAs({"angleData": [180]}, source, output_path=output)


if __name__ == "__main__":
    unittest.main()
