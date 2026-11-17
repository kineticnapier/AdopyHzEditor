from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from core.note_model import Note
from web_ui import Bridge


class FixedAngleDiskExportTests(TestCase):
    def test_dialog_export_writes_fixed_angle_to_real_adofai_files(self):
        bridge = Bridge()
        bridge.notes = [Note(0.0, 0.073, 69.0).normalized()]

        angle_data = {}
        with TemporaryDirectory() as directory:
            for angle in (90.0, 135.0):
                # The real save path is exercised; only the native file chooser
                # is replaced, so no desktop window is required in CI.
                target = Path(directory) / f"fixed-{int(angle)}"
                with patch.object(bridge, "_dialog", return_value=str(target)):
                    result = bridge.export_adofai_advanced(
                        {
                            "method": "rabbit_zip",
                            "angleCompressionMode": "fixed",
                            "angleCompressionFixedAngle": angle,
                            "xMode": "floor",
                            "finalAngleMode": "horizontal",
                            "useProjectSong": False,
                            "copyProjectSong": False,
                        }
                    )
                written = target.with_suffix(".adofai")
                self.assertTrue(result["ok"])
                self.assertEqual(Path(result["path"]), written)
                self.assertTrue(written.is_file())
                level = json.loads(written.read_text(encoding="utf-8"))
                self.assertTrue(level["angleData"])
                angle_data[angle] = level["angleData"]

        self.assertNotEqual(angle_data[90.0], angle_data[135.0])
        self.assertIsNone(bridge.notes[0].target_angle)
