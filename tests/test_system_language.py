"""On first launch the language follows Windows' display language."""

from __future__ import annotations

import unittest
from unittest import mock

import i18n


class SystemLanguageTests(unittest.TestCase):
    def test_windows_display_language_decides(self):
        with mock.patch.object(i18n, "_windows_ui_language_is_japanese", return_value=True):
            self.assertEqual(i18n.system_default_language(), "ja")
        with mock.patch.object(i18n, "_windows_ui_language_is_japanese", return_value=False):
            self.assertEqual(i18n.system_default_language(), "en")

    def test_other_systems_use_the_locale(self):
        with mock.patch.object(i18n, "_windows_ui_language_is_japanese", return_value=None), \
                mock.patch.object(i18n.locale, "getlocale", return_value=("ja_JP", "UTF-8")):
            self.assertEqual(i18n.system_default_language(), "ja")
        with mock.patch.object(i18n, "_windows_ui_language_is_japanese", return_value=None), \
                mock.patch.object(i18n.locale, "getlocale", return_value=("en_US", "UTF-8")):
            self.assertEqual(i18n.system_default_language(), "en")


if __name__ == "__main__":
    unittest.main()
