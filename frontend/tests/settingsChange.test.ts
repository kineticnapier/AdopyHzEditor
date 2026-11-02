import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { hasEffectiveSettingsChange } from "../src/settings/settingsChange.ts";

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
  const guard = patch.indexOf("if (!hasEffectiveSettingsChange(settings, changes)) return;");
  const dirty = patch.indexOf("setDirty(true)");
  const queue = patch.indexOf("pendingSettings.current =");
  assert.ok(guard >= 0 && dirty > guard && queue > dirty,
    "no-op guard must precede the dirty flag and API queue");
});
