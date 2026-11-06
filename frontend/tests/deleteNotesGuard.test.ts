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

test("a pending destructive edit rejects another kind of destructive edit", async () => {
  for (const firstKind of ["delete", "cut", "range-cut"]) {
    const guard = new AsyncActionGuard();
    const notes = ["A", "B", "C", "D"];
    let releaseFirst!: () => void;
    const barrier = new Promise<void>(resolve => { releaseFirst = resolve; });
    const first = guard.run(async () => {
      await barrier;
      notes.splice(0, 1);
    });
    for (const secondKind of ["delete", "cut", "range-cut"]) {
      assert.equal(await guard.run(async () => { notes.splice(2, 1); }), false,
        `${firstKind} must block ${secondKind}`);
    }
    releaseFirst();
    assert.equal(await first, true);
    assert.deepEqual(notes, ["B", "C", "D"]);
    assert.equal(await guard.run(async () => { notes.splice(1, 1); }), true);
    assert.deepEqual(notes, ["B", "D"]);
  }
});

test("App shares one guard across delete, cut and range-cut", () => {
  const app = readFileSync(new URL("../src/App.tsx", import.meta.url), "utf8");
  assert.match(app, /const destructiveSelection = useRef\(new AsyncActionGuard\(\)\)/);
  for (const [startMarker, endMarker, apiCall] of [
    ["  async function deleteNotes(", "  async function cutRange(", "delete_notes"],
    ["  async function cutRange(", "  async function duplicate(", "cut_notes_range"],
    ["  async function cutSelected(", "  async function pasteAtPlayback(", "cut_notes"],
  ] as const) {
    const start = app.indexOf(startMarker);
    const end = app.indexOf(endMarker, start);
    assert.ok(start >= 0 && end > start, startMarker);
    const block = app.slice(start, end);
    assert.match(block, /await destructiveSelection\.current\.run\(async \(\) => \{/);
    assert.match(block, new RegExp(`api\\.${apiCall}\\(`));
    assert.match(block, /await queuedMutation\(/);
  }
  assert.doesNotMatch(app, /deletingSelection/);
});
