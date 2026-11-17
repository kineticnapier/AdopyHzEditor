import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";

const app = readFileSync(new URL("../src/App.tsx", import.meta.url), "utf8");

function actionSource(name: string, nextName: string): string {
  const start = app.indexOf(`  async function ${name}()`);
  const end = app.indexOf(`  async function ${nextName}(`, start);
  assert.ok(start >= 0 && end > start, `could not locate ${name}`);
  return app.slice(start, end);
}

test("empty Ctrl+C does not queue a no-op backend copy", () => {
  const source = actionSource("copySelected", "cutSelected");
  assert.match(source, /if \(api && selected\.length\)\s*\{/);
  assert.ok(source.indexOf("if (api && selected.length)") < source.indexOf("enqueueAppliedTask("));
  assert.match(source, /api\.copy_notes\(selected\)/);
});

test("empty Ctrl+Alt+A does not queue a no-op target-angle update", () => {
  const source = actionSource("applyTargetAngle", "queuedPlaybackAction");
  assert.match(source, /if \(api && selected\.length\)\s*await queuedSelectionMutation\(/);
  assert.ok(source.indexOf("if (api && selected.length)") < source.indexOf("queuedSelectionMutation("));
  assert.match(source, /api\.apply_target_angle\(selected, settings\.targetAngle\)/);
});
