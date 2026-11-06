import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { AsyncActionGuard } from "../src/api/requestCoordinator.ts";

test("a pending deletion blocks a disjoint index deletion until the first settles", async () => {
  const guard = new AsyncActionGuard();
  const notes = ["A", "B", "C", "D"];
  let releaseFirst!: () => void;
  const firstBarrier = new Promise<void>(resolve => { releaseFirst = resolve; });
  const first = guard.run(async () => {
    await firstBarrier;
    notes.splice(0, 1);
  });
  assert.equal(guard.isRunning, true);
  // Both index sets are distinct, but the first deletion shifts the second.
  const second = await guard.run(async () => { notes.splice(2, 1); });
  assert.equal(second, false);
  releaseFirst();
  assert.equal(await first, true);
  assert.deepEqual(notes, ["B", "C", "D"]);
  assert.equal(guard.isRunning, false);
  assert.equal(await guard.run(async () => { notes.splice(1, 1); }), true);
  assert.deepEqual(notes, ["B", "D"]);
});

test("App uses a single-flight guard for every deleteNotes request", () => {
  const app = readFileSync(new URL("../src/App.tsx", import.meta.url), "utf8");
  assert.match(app, /const deletingSelection = useRef\(new AsyncActionGuard\(\)\)/);
  const start = app.indexOf("  async function deleteNotes(");
  const end = app.indexOf("  async function cutRange(", start);
  assert.ok(start >= 0 && end > start);
  const deletion = app.slice(start, end);
  assert.match(deletion, /await deletingSelection\.current\.run\(async \(\) => \{/);
  assert.match(deletion, /await queuedMutation\(/);
  assert.doesNotMatch(deletion, /deletingSelection\.current === key/);
});
