import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { createSelectionMutationGuard } from "../src/editor/selectionMutationGuard.ts";

function deferred() {
  let resolve!: () => void;
  const promise = new Promise<void>((r) => { resolve = r; });
  return { promise, resolve };
}

// Audit #1: a second cut/delete issued before React re-rendered reused the old
// selection indices and removed different notes that had shifted into them.
test("a destructive action on a selection runs once while it is in flight", async () => {
  const guard = createSelectionMutationGuard();
  const gate = deferred();
  const runs: string[] = [];
  const first = guard.run([2, 0], async () => { runs.push("cut"); await gate.promise; });
  const repeated = guard.run([0, 2], async () => { runs.push("cut"); });
  const deleted = guard.run([2, 0], async () => { runs.push("delete"); });
  const overlapping = guard.run([2, 5], async () => { runs.push("overlap"); });
  assert.equal(await repeated, false);
  assert.equal(await deleted, false);
  assert.equal(await overlapping, false);
  gate.resolve();
  assert.equal(await first, true);
  assert.deepEqual(runs, ["cut"]);
});

test("the guard is released after success or failure", async () => {
  const guard = createSelectionMutationGuard();
  await assert.rejects(guard.run([1], async () => { throw new Error("boom"); }), /boom/);
  const runs: number[] = [];
  assert.equal(await guard.run([1], async () => { runs.push(1); }), true);
  assert.equal(await guard.run([1], async () => { runs.push(2); }), true);
  assert.deepEqual(runs, [1, 2]);
});

test("different selections and empty selections are handled independently", async () => {
  const guard = createSelectionMutationGuard();
  const gate = deferred();
  const runs: string[] = [];
  const a = guard.run([0], async () => { runs.push("a"); await gate.promise; });
  assert.equal(await guard.run([1], async () => { runs.push("b"); }), true);
  assert.equal(await guard.run([], async () => { runs.push("empty"); }), false);
  gate.resolve();
  await a;
  assert.deepEqual(runs, ["a", "b"]);
});

test("App routes cut and delete through the shared selection guard", () => {
  const source = readFileSync(new URL("../src/App.tsx", import.meta.url), "utf8");
  assert.match(source, /async function cutSelected\(\)[\s\S]*?destructiveSelection\.current\.run\(\s*indices/);
  assert.match(source, /async function deleteNotes\([\s\S]*?destructiveSelection\.current\.run\(\s*indices/);
});
