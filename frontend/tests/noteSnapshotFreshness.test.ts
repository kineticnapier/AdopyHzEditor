import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { enqueueAppliedTask, SerialTaskQueue } from "../src/api/requestCoordinator.ts";

test("a queued selection edit does not use indices after an earlier note replacement", async () => {
  const queue = new SerialTaskQueue();
  let committedNotes = ["A", "B", "C"];
  const renderedNotes = committedNotes;
  let releaseFirst!: () => void;
  const barrier = new Promise<void>(resolve => { releaseFirst = resolve; });
  const first = enqueueAppliedTask(
    queue,
    async () => { await barrier; return ["B", "C"]; },
    next => { committedNotes = next; },
  );
  let staleCalls = 0;
  const stale = enqueueAppliedTask(
    queue,
    async () => { staleCalls += 1; return ["B"]; },
    next => { committedNotes = next; },
    () => committedNotes === renderedNotes,
  );
  releaseFirst();
  assert.deepEqual(await first, ["B", "C"]);
  assert.equal(await stale, undefined);
  assert.equal(staleCalls, 0);
  assert.deepEqual(committedNotes, ["B", "C"]);
});

test("an old render's selection callback stays invalid until the new notes render", async () => {
  const queue = new SerialTaskQueue();
  const renderedNotes = ["A", "B", "C"];
  let committedNotes = ["B", "C"];
  let staleCalls = 0;
  const result = await enqueueAppliedTask(
    queue,
    async () => { staleCalls += 1; return ["C"]; },
    next => { committedNotes = next; },
    () => committedNotes === renderedNotes,
  );
  assert.equal(result, undefined);
  assert.equal(staleCalls, 0);
  assert.deepEqual(committedNotes, ["B", "C"]);
  const freshRenderNotes = committedNotes;
  assert.deepEqual(await enqueueAppliedTask(
    queue,
    async () => ["C"],
    next => { committedNotes = next; },
    () => committedNotes === freshRenderNotes,
  ), ["C"]);
});

test("App tracks the latest applied notes and rejects stale selection requests", () => {
  const app = readFileSync(new URL("../src/App.tsx", import.meta.url), "utf8");
  assert.match(app, /const latestNotes = useRef\(notes\)/);
  assert.match(app, /latestNotes\.current = state\.notes;\s*setNotes\(state\.notes\)/);
  assert.match(app, /latestNotes\.current = result\.notes;\s*setNotes\(result\.notes\)/);
  const queued = app.slice(app.indexOf("  async function queuedMutation("), app.indexOf("  function queueExternalMutation("));
  assert.match(queued, /const snapshot = notes;/);
  assert.match(queued, /latestNotes\.current === snapshot/);
  assert.match(queued, /enqueueAppliedTask\(/);
  assert.match(queued, /isCurrent,/);
  for (const name of [
    "moveNotes", "duplicateMove", "resizeNotes", "deleteNotes",
    "cutRange", "duplicate", "quantize", "splitSelected",
    "cutSelected", "applyTargetAngle",
  ]) {
    const start = app.indexOf(`  async function ${name}(`);
    const end = app.indexOf("\n  }", start);
    assert.ok(start >= 0 && end > start, name);
    assert.match(app.slice(start, end), /queuedSelectionMutation\(/, name);
  }
  assert.match(app, /return queuedSelectionMutation\(call, selection\);/);
});
