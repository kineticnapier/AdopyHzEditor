import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { presetInsertSelection } from "../src/settings/presetSelection.ts";
import { LatestRequestGate } from "../src/api/requestCoordinator.ts";

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

test("preset tab uses a single-row three-column inspector navigation", () => {
  const settings = readFileSync(new URL("../src/settings/SettingsPanel.tsx", import.meta.url), "utf8");
  const css = readFileSync(new URL("../src/settings/presets.css", import.meta.url), "utf8");
  assert.match(settings, /className="inspector-tabs"/);
  assert.match(settings, /onClick=\{\(\) => setPage\("presets"\)\}/);
  assert.match(css, /\.settings nav\.inspector-tabs\s*\{\s*grid-template-columns:\s*repeat\(3,\s*minmax\(0,\s*1fr\)\)/);
});

test("late initial preset fetch cannot replace a saved or deleted list", async () => {
  const gate = new LatestRequestGate();
  let release!: (value: string[]) => void;
  const initial = new Promise<string[]>((resolve) => { release = resolve; });
  const request = gate.issue();
  let visible = ["old"];
  const pending = initial.then((items) => {
    if (gate.isCurrent(request)) visible = items;
  });
  gate.invalidate(); // successful save/delete applies a newer list
  visible = ["new"];
  release(["old"]);
  await pending;
  assert.deepEqual(visible, ["new"]);
});

test("preset panel invalidates pending fetch after writes and on unmount", () => {
  const panel = readFileSync(new URL("../src/settings/NotePresetPanel.tsx", import.meta.url), "utf8");
  assert.match(panel, /if \(!alive \|\| !listRequests\.current\.isCurrent\(request\)\) return;/);
  assert.equal((panel.match(/listRequests\.current\.invalidate\(\);/g) ?? []).length, 3);
});
