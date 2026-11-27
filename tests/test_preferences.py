"""App-wide preferences (環境設定) and what they change."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from core.note_model import Note
from web import preferences
from web.preferences import is_newer_version, load_preferences, parse_preferences


def _bridge(prefs_file: Path | None = None):
    from web_ui import Bridge

    bridge = Bridge()
    bridge._preferences_file = prefs_file
    return bridge


class PreferenceFileTests(unittest.TestCase):
    def test_broken_values_fall_back_to_defaults(self):
        prefs = parse_preferences({"kpsLimit": "fast", "newProject": {"bpm": 120, "volume": 3}, "lastProject": 5})
        self.assertEqual(prefs["kpsLimit"], 200.0)
        self.assertEqual(prefs["newProject"], {"bpm": 120})
        self.assertIsNone(prefs["lastProject"])
        self.assertEqual(parse_preferences(None)["checkUpdates"], False)

    def test_saving_keeps_the_language_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            path.write_text(json.dumps({"language": "ja"}), encoding="utf-8")
            bridge = _bridge(path)
            bridge.set_preferences({"kpsLimit": 150, "checkUpdates": True})
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data["language"], "ja")
            self.assertEqual(load_preferences(path)["kpsLimit"], 150.0)
            self.assertTrue(bridge.get_preferences()["checkUpdates"])

    def test_without_a_file_nothing_is_written(self):
        bridge = _bridge()
        with mock.patch.object(preferences, "save_preferences") as save:
            bridge.set_preferences({"kpsLimit": 300})
        save.assert_not_called()
        self.assertEqual(bridge.get_preferences()["kpsLimit"], 300.0)

    def test_bad_values_are_rejected_before_saving(self):
        bridge = _bridge()
        with self.assertRaises(ValueError):
            bridge.set_preferences({"kpsLimit": 0, "checkUpdates": True})
        self.assertFalse(bridge.get_preferences()["checkUpdates"])
        with self.assertRaises(ValueError):
            bridge.set_preferences({"language": "xx"})


class NewProjectDefaultsTests(unittest.TestCase):
    def test_startup_applies_defaults_once_and_only_to_an_empty_document(self):
        bridge = _bridge()
        bridge.set_preferences({"newProject": {"bpm": 200, "exportOctave": 9, "colormap": "gray", "volume": 1}})
        self.assertEqual(bridge.get_preferences()["newProject"]["exportOctave"], 4)  # clamped
        result = bridge.apply_startup_preferences()
        self.assertEqual(result["state"]["settings"]["bpm"], 200.0)
        self.assertEqual(result["state"]["settings"]["colormap"], "gray")
        self.assertNotEqual(bridge.settings["volume"], 1)
        self.assertFalse(result["state"]["dirty"])
        bridge.settings["bpm"] = 90.0
        bridge.apply_startup_preferences()
        self.assertEqual(bridge.settings["bpm"], 90.0)

    def test_startup_leaves_existing_work_alone(self):
        bridge = _bridge()
        bridge.set_preferences({"newProject": {"bpm": 200}})
        bridge.notes = [Note(0.0, 1.0, 60.0)]
        bridge.apply_startup_preferences()
        self.assertNotEqual(bridge.settings["bpm"], 200.0)


class ReopenTests(unittest.TestCase):
    def test_saved_project_is_remembered_and_reopened(self):
        with tempfile.TemporaryDirectory() as tmp:
            prefs_file = Path(tmp) / "settings.json"
            first = _bridge(prefs_file)
            first.notes = [Note(1.0, 2.0, 64.0)]
            first._save_project_path(str(Path(tmp) / "song"))
            self.assertTrue(load_preferences(prefs_file)["lastProject"].endswith("song.adopyhz"))

            first.set_preferences({"reopenLastProject": True})
            second = _bridge(prefs_file)
            result = second.apply_startup_preferences()
            self.assertIsNotNone(result["reopened"])
            self.assertEqual(len(result["state"]["notes"]), 1)

    def test_missing_last_project_is_reported_not_raised(self):
        bridge = _bridge()
        bridge.set_preferences({"reopenLastProject": True})
        bridge._preferences_memory["lastProject"] = str(Path(tempfile.gettempdir()) / "gone.adopyhz")
        result = bridge.apply_startup_preferences()
        self.assertIsNone(result["reopened"])
        self.assertIn("見つかりません", result["state"]["status"])


class ExportDefaultsTests(unittest.TestCase):
    def test_saved_export_choices_come_back_except_document_values(self):
        bridge = _bridge()
        options = bridge.get_adofai_export_defaults()
        options.update(method="harmony", fixedX=3.5, songOffsetMs=999.0, targetBpm=1.0, appendToChart="no")
        bridge.save_adofai_export_defaults(options)
        again = bridge.get_adofai_export_defaults()
        self.assertEqual(again["method"], "harmony")
        self.assertEqual(again["fixedX"], 3.5)
        self.assertNotEqual(again["songOffsetMs"], 999.0)
        self.assertNotEqual(again["targetBpm"], 1.0)
        self.assertIs(again["appendToChart"], True)  # wrong type is not kept
        self.assertTrue(bridge.get_preferences()["hasExportDefaults"])
        bridge.clear_adofai_export_defaults()
        self.assertEqual(bridge.get_adofai_export_defaults()["method"], "rabbit_zip")

    def test_kps_limit_follows_the_preference(self):
        bridge = _bridge()
        self.assertEqual(bridge._kps_limit(), 200.0)
        bridge.set_preferences({"kpsLimit": 1000})
        self.assertEqual(bridge._kps_limit(), 1000.0)


class UpdateCheckTests(unittest.TestCase):
    def test_version_comparison(self):
        self.assertTrue(is_newer_version("1.0.1", "1.0.0"))
        self.assertTrue(is_newer_version("v1.10.0", "1.9.9"))
        self.assertFalse(is_newer_version("1.0.0", "1.0.0"))
        self.assertFalse(is_newer_version("0.9.0", "1.0.0"))

    def test_check_reports_failures_instead_of_raising(self):
        bridge = _bridge()
        with mock.patch.object(preferences, "fetch_latest_release", side_effect=OSError("offline")):
            result = bridge.check_for_update()
        self.assertFalse(result["ok"])
        self.assertIn("offline", result["error"])
        with mock.patch.object(preferences, "fetch_latest_release", return_value={"version": "99.0.0", "url": "u"}):
            self.assertTrue(bridge.check_for_update()["newer"])


if __name__ == "__main__":
    unittest.main()
