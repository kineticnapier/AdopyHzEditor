"""Backend status messages follow the language chosen in 環境設定."""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from core.note_model import Note
from i18n import current_language, set_language, tr

ROOT = Path(__file__).resolve().parents[1]


class BackendMessageTests(unittest.TestCase):
    def tearDown(self):
        set_language("ja", save=False)

    def test_every_message_key_is_in_both_locales(self):
        used = set()
        for path in [*ROOT.glob("web/*.py"), ROOT / "web_ui.py", *ROOT.glob("exporters/*.py"), *ROOT.glob("core/*.py")]:
            used |= set(re.findall(r'tr\(\s*"(msg\.[a-z0-9_]+)"', path.read_text(encoding="utf-8")))
        self.assertGreater(len(used), 50)
        for lang in ("ja", "en"):
            table = json.loads((ROOT / "locales" / f"{lang}.json").read_text(encoding="utf-8"))
            self.assertEqual(sorted(used - set(table)), [], lang)

    def test_status_follows_the_language(self):
        from web_ui import Bridge

        self.assertEqual(current_language(), "ja")
        bridge = Bridge()
        bridge.notes = [Note(0.0, 1.0, 60.0), Note(1.0, 2.0, 62.0)]
        self.assertEqual(bridge.delete_notes([0])["status"], "1個のノートを削除しました")
        set_language("en", save=False)
        self.assertEqual(bridge.delete_notes([0])["status"], "Deleted 1 notes")
        self.assertEqual(tr("msg.no_selection"), "No notes are selected")


if __name__ == "__main__":
    unittest.main()
