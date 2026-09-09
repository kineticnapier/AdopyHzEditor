from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

from core.project_io import load_project, save_project
from web_ui import Bridge


NON_DEFAULT_SETTINGS = {
    "volume": 61,
    "speed": 1.75,
    "notePreview": False,
    "previewVolume": 43,
    "previewOctave": 2,
    "previewSound": "square",
    "exportOctave": -1,
    "exportSemitone": 7,
    "gridEnabled": True,
    "metronomeEnabled": True,
    "bpm": 231.5,
    "offsetMs": -123.25,
    "metronomeVolume": 67,
    "snapEnabled": True,
    "snapDiv": 8,
    "contrast": 184,
    "gamma": 132,
    "enhance": False,
    "displayMode": "harmonic",
    "harmonics": "all",
    "colormap": "magma",
    "analysisProfile": "Deep",
    "cqtResolution": "48 bins/octave",
    "curveShape": "smoothstep",
    "curveInterpolation": "bezier_hz",
    "targetAngle": 137.5,
}


class ProjectSettingsRoundTripTests(unittest.TestCase):
    def test_all_web_project_settings_round_trip(self):
        source = Bridge()
        self.assertEqual(set(source.settings), set(NON_DEFAULT_SETTINGS))
        source.update_settings(NON_DEFAULT_SETTINGS)

        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir) / "settings.adopyhz"
            save_project(
                project,
                audio_path=None,
                notes=[],
                settings=source._project_settings(),
            )
            _audio, _notes, saved_settings = load_project(project)

        restored = Bridge()
        restored._apply_project_settings(saved_settings)

        self.assertEqual(restored.settings, source.settings)

    def test_missing_new_setting_keys_keep_existing_defaults(self):
        bridge = Bridge()
        defaults = {
            key: bridge.settings[key]
            for key in ("contrast", "gamma", "enhance", "harmonics", "targetAngle")
        }

        bridge._apply_project_settings({"grid_bpm": 240.0})

        self.assertEqual(bridge.settings["bpm"], 240.0)
        for key, expected in defaults.items():
            self.assertEqual(bridge.settings[key], expected)


if __name__ == "__main__":
    unittest.main()
