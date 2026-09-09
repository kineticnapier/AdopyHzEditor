from __future__ import annotations

import unittest
from unittest import mock

import web_ui


class WebviewRendererTests(unittest.TestCase):
    def test_windows_source_and_packaged_runs_default_to_qt(self):
        with (
            mock.patch.object(web_ui.sys, "platform", "win32"),
            mock.patch.dict(web_ui.os.environ, {}, clear=True),
        ):
            self.assertEqual(web_ui._webview_gui(), "qt")
            with mock.patch.object(web_ui.sys, "frozen", True, create=True):
                self.assertEqual(web_ui._webview_gui(), "qt")

    def test_non_windows_keeps_automatic_backend_selection(self):
        with (
            mock.patch.object(web_ui.sys, "platform", "linux"),
            mock.patch.dict(web_ui.os.environ, {}, clear=True),
        ):
            self.assertIsNone(web_ui._webview_gui())

    def test_explicit_renderer_override_is_respected(self):
        with (
            mock.patch.object(web_ui.sys, "platform", "win32"),
            mock.patch.dict(
                web_ui.os.environ,
                {"ADOPY_WEB_UI_GUI": "edgechromium"},
                clear=True,
            ),
        ):
            self.assertEqual(web_ui._webview_gui(), "edgechromium")

    def test_auto_override_restores_platform_default(self):
        with (
            mock.patch.object(web_ui.sys, "platform", "win32"),
            mock.patch.dict(
                web_ui.os.environ,
                {"ADOPY_WEB_UI_GUI": "auto"},
                clear=True,
            ),
        ):
            self.assertIsNone(web_ui._webview_gui())


if __name__ == "__main__":
    unittest.main()
