import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { presetInsertSelection } from "../src/settings/presetSelection.ts";

test("preset insertion selects the single newly inserted note", () => {
  assert.deepEqual(presetInsertSelection({ index: 4 }), [4]);
  assert.deepEqual(presetInsertSelection({ index: 0 }), [0]);
});

test("preset insertion respects the backend's explicit multiple indices", () => {
  assert.deepEqual(presetInsertSelection({ index: 4, indices: [2, 3] }), [2, 3]);
  assert.deepEqual(presetInsertSelection({ index: 4, indices: [] }), []);
  assert.deepEqual(presetInsertSelection({}), []);
});

test("preset panel is reachable and uses the same mutation queue as the editor", () => {
  const settings = readFileSync(new URL("../src/settings/SettingsPanel.tsx", import.meta.url), "utf8");
  const app = readFileSync(new URL("../src/App.tsx", import.meta.url), "utf8");
  const presets = readFileSync(new URL("../src/settings/NotePresetPanel.tsx", import.meta.url), "utf8");
  assert.match(settings, /page === "presets"\s*&&\s*\(/);
  assert.match(settings, /<NotePresetPanel\s/);
  assert.match(settings, /onQueuedMutation=\{onQueuedMutation\}/);
  assert.match(app, /playbackTime=\{playback\.time\}/);
  assert.match(app, /onQueuedPresetAction=\{queuePresetAction\}/);
  assert.match(presets, /await onQueuedMutation\(/);
  assert.match(presets, /await onQueuedPresetAction\(/);
});
