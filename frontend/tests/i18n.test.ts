import assert from "node:assert/strict";
import test from "node:test";
import { en } from "../src/i18n/en.ts";
import { getLanguage, normalizeLanguage, setLanguage, t } from "../src/i18n/index.ts";
import { ja } from "../src/i18n/ja.ts";
import { workspaceTitle } from "../src/editor/emptyState.ts";
import { playbackStatusMessage } from "../src/components/playbackStatusMessage.ts";
import { selectionStatusText } from "../src/editor/selectionAnnouncement.ts";

test("both languages have every key and no empty text", () => {
  assert.deepEqual(Object.keys(en).sort(), Object.keys(ja).sort());
  for (const [key, text] of [...Object.entries(ja), ...Object.entries(en)])
    assert.ok(text.trim(), `${key} is empty`);
});

test("switching the language changes the text, with parameters filled in", () => {
  try {
    assert.equal(getLanguage(), "ja");
    assert.equal(t("panel.notes_selected", { count: 3 }), "3個選択中");
    setLanguage("en");
    assert.equal(t("panel.notes_selected", { count: 3 }), "3 selected");
    assert.equal(t("menu.file"), "File");
    assert.equal(workspaceTitle(null, false), "Empty workspace");
    assert.equal(playbackStatusMessage({ available: false, error: "boom" }), "Playback error: boom");
    const notes = [{ start: 1.25, end: 2, midi: 60 }, { start: 2.5, end: 3, midi: 64 }] as never;
    assert.equal(selectionStatusText(notes, [0, 1], [], null), "2 notes selected (#1, #2)");
    assert.equal(selectionStatusText(notes, [], [], null), "Nothing selected");
  } finally {
    setLanguage("ja");
  }
  assert.equal(t("menu.file"), "ファイル");
});

test("unknown languages fall back to Japanese", () => {
  assert.equal(normalizeLanguage("fr"), "ja");
  assert.equal(normalizeLanguage(undefined), "ja");
  assert.equal(normalizeLanguage("en"), "en");
});
