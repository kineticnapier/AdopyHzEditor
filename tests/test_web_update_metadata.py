from __future__ import annotations

import unittest
from unittest import mock

from app_metadata import APP_VERSION
import web.tools as web_tools


class WebUpdateMetadataTests(unittest.TestCase):
    def test_update_info_uses_application_version(self):
        info = web_tools.ToolsMixin().get_update_info()
        self.assertEqual(info["version"], APP_VERSION)

    def test_translation_receives_application_version(self):
        def fake_tr(key: str, **values):
            return f"{key}:{values.get('version', '')}"

        with mock.patch.object(web_tools, "tr", side_effect=fake_tr) as translate:
            info = web_tools.ToolsMixin().get_update_info()

        self.assertEqual(info["text"], f"update.open_releases_text:{APP_VERSION}")
        translate.assert_any_call("update.open_releases_text", version=APP_VERSION)

    def test_update_info_follows_the_shared_version_constant(self):
        with mock.patch.object(web_tools, "APP_VERSION", "9.8.7"):
            info = web_tools.ToolsMixin().get_update_info()

        self.assertEqual(info["version"], "9.8.7")
        self.assertIn("9.8.7", info["text"])


if __name__ == "__main__":
    unittest.main()
