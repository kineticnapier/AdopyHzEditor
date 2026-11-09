import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { acceptSettingsPatch, hasEffectiveSettingsChange } from "../src/settings/settingsChange.ts";

test("empty and identical settings patches do not count as edits", () => {
  const settings = { volume: 85, snapDiv: 1, notePreview: false };
  assert.equal(hasEffectiveSettingsChange(settings, {}), false);
  assert.equal(hasEffectiveSettingsChange(settings, { volume: 85 }), false);
  assert.equal(hasEffectiveSettingsChange(settings, { notePreview: false, snapDiv: 1 }), false);
});

test("real changes, including false and zero, are still detected", () => {
  const settings = { volume: 85, snapDiv: 1, notePreview: true };
  assert.equal(hasEffectiveSettingsChange(settings, { volume: 0 }), true);
  assert.equal(hasEffectiveSettingsChange(settings, { notePreview: false }), true);
  assert.equal(hasEffectiveSettingsChange(settings, { snapDiv: 2 }), true);
  assert.equal(hasEffectiveSettingsChange(settings, { volume: 85, snapDiv: 2 }), true);
});

test("App.patch checks for a real change before dirtying or sending settings", () => {
  const source = readFileSync(new URL("../src/App.tsx", import.meta.url), "utf8");
  const start = source.indexOf("  async function patch(changes: Partial<EditorSettings>) {");
  const end = source.indexOf("  async function flushPendingSettings()", start);
  assert.ok(start >= 0 && end > start, "settings patch function exists");
  const patch = source.slice(start, end);
  const guard = patch.indexOf("if (!acceptSettingsPatch(settingsSnapshotRef, changes)) return;");
  const dirty = patch.indexOf("setDirty(true)");
  const queue = patch.indexOf("pendingSettings.current =");
  assert.ok(guard >= 0 && dirty > guard && queue > dirty,
    "no-op guard must precede the dirty flag and API queue");
});

test("rapid settings reversals are queued before a React render", () => {
  const snapshot = { current: { volume: 85, snapDiv: 1, notePreview: false } };
  assert.equal(acceptSettingsPatch(snapshot, { volume: 90 }), true);
  assert.equal(snapshot.current.volume, 90);
  // The old React render still contains 85; the reversal must not be dropped.
  assert.equal(acceptSettingsPatch(snapshot, { volume: 85 }), true);
  assert.equal(snapshot.current.volume, 85);
  assert.equal(acceptSettingsPatch(snapshot, { volume: 85 }), false);
  assert.equal(acceptSettingsPatch(snapshot, {}), false);
  assert.equal(acceptSettingsPatch(snapshot, { snapDiv: 2, notePreview: true }), true);
  assert.deepEqual(snapshot.current, { volume: 85, snapDiv: 2, notePreview: true });
});

test("App keeps the settings snapshot aligned with document loads and API replies", () => {
  const source = readFileSync(new URL("../src/App.tsx", import.meta.url), "utf8");
  assert.match(source, /const settingsSnapshotRef = useRef\(settings\)/);
  assert.match(source, /settingsSnapshotRef\.current = state\.settings;\s*setSettings\(state\.settings\)/);
  assert.match(source, /settingsSnapshotRef\.current = normalized;\s*setSettings\(normalized\)/);
  assert.match(source, /settingsSnapshotRef\.current = recovered;\s*setSettings\(recovered\)/);
  assert.match(source, /changes\.analysisSource !== previousSettings\.analysisSource/);
});

test("settings stay unsent until the backend has loaded its initial state", () => {
  const source = readFileSync(new URL("../src/App.tsx", import.meta.url), "utf8");
  const connectionStart = source.indexOf("const ping = await backend.ping()");
  const pingGuard = source.indexOf("if (!ping.ok) throw new Error", connectionStart);
  const stateRead = source.indexOf("const state = await backend.get_state()", connectionStart);
  const stateApplied = source.indexOf("applyState(state)", stateRead);
  const apiPublished = source.indexOf("setApi(backend)", stateApplied);
  const connectionPublished = source.indexOf("setConnected(ping.ok)", apiPublished);
  assert.ok(connectionStart >= 0 && pingGuard > connectionStart &&
    stateRead > pingGuard && stateApplied > stateRead && apiPublished > stateApplied &&
    connectionPublished > apiPublished,
  "controls must not receive a backend API before get_state succeeds");

  const patchStart = source.indexOf("async function patch(changes: Partial<EditorSettings>)");
  const patchEnd = source.indexOf("async function flushPendingSettings()", patchStart);
  assert.ok(patchStart >= 0 && patchEnd > patchStart);
  const patch = source.slice(patchStart, patchEnd);
  const readyGuard = patch.indexOf("if (!api || !connected)");
  const snapshotMutation = patch.indexOf("acceptSettingsPatch(settingsSnapshotRef, changes)");
  const dirty = patch.indexOf("setDirty(true)");
  assert.ok(readyGuard >= 0 && snapshotMutation > readyGuard && dirty > snapshotMutation,
    "a disconnected edit must not change the settings snapshot or dirty flag");
});
