import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { settingsResponseIsCurrent } from "../src/settings/settingsResponseFreshness.ts";

test("settings responses require the latest request and the same document", () => {
  assert.equal(settingsResponseIsCurrent(true, false, 5, 5), true);
  assert.equal(settingsResponseIsCurrent(false, false, 5, 5), false);
  assert.equal(settingsResponseIsCurrent(true, true, 5, 5), false);
  assert.equal(settingsResponseIsCurrent(true, false, 5, 6), false);
});

test("a newer slider edit or document change invalidates an in-flight recovery", () => {
  const requestGeneration = 7;
  let currentGeneration = 7;
  let pendingChanges = false;
  assert.equal(settingsResponseIsCurrent(true, pendingChanges, requestGeneration, currentGeneration), true);
  // Recovery read starts. A newer optimistic setting is entered before it finishes.
  pendingChanges = true;
  assert.equal(settingsResponseIsCurrent(true, pendingChanges, requestGeneration, currentGeneration), false);
  pendingChanges = false;
  currentGeneration += 1;
  assert.equal(settingsResponseIsCurrent(true, pendingChanges, requestGeneration, currentGeneration), false);
});

test("App rechecks settings freshness after awaiting recovery", () => {
  const app = readFileSync(new URL("../src/App.tsx", import.meta.url), "utf8");
  const start = app.indexOf("  async function flushPendingSettings() {");
  const end = app.indexOf("  async function applyViewAction(", start);
  assert.ok(start >= 0 && end > start, "settings flush boundaries exist");
  const block = app.slice(start, end);
  assert.match(block, /const requestGeneration = documentGeneration\.current;/);
  assert.match(block, /const isCurrent = \(\) =>\s*settingsResponseIsCurrent\(/);
  assert.match(block, /if \(isCurrent\(\)\) \{\s*settingsSnapshotRef\.current = normalized;\s*setSettings\(normalized\);\s*\}/);
  assert.match(block, /const recovered = \(await api\.get_state\(\)\)\.settings;[\s\S]*?if \(isCurrent\(\)\) \{\s*settingsSnapshotRef\.current = recovered;\s*setSettings\(recovered\);\s*\}/);
});
