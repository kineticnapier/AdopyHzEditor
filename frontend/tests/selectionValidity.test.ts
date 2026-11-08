import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { retainValidSelection, selectionAfterMutation } from "../src/editor/selectionValidity.ts";

test("unchanged selection retains identity across backend state refresh", () => {
  const selected = [0, 3, 7];
  assert.strictEqual(retainValidSelection(selected, 8), selected);
  const empty: number[] = [];
  assert.strictEqual(retainValidSelection(empty, 0), empty);
});

test("removed notes are filtered without mutating the original selection", () => {
  const selected = [0, 3, 7];
  assert.deepEqual(retainValidSelection(selected, 4), [0, 3]);
  assert.deepEqual(selected, [0, 3, 7]);
  assert.deepEqual(retainValidSelection(selected, 0), []);
});

test("fractional, non-finite and unsafe note indices are discarded", () => {
  const selected = [0, .5, NaN, 2, Infinity, -Infinity, Number.MAX_SAFE_INTEGER + 1];
  assert.deepEqual(retainValidSelection(selected, 3), [0, 2]);
  assert.deepEqual(selected.slice(0, 4), [0, .5, NaN, 2]);
  const valid = [0, 2];
  assert.strictEqual(retainValidSelection(valid, 3), valid);
});

test("explicit mutation selections use the same safe-index filter as state refresh", () => {
  // A backend mutation may supply an explicit index list. Fractional indices
  // must not bypass the validation used for an existing selection.
  const source = readFileSync(new URL("../src/App.tsx", import.meta.url), "utf8");
  const mutation = source.match(/function applyMutation\([\s\S]*?\n  }\n  async function queuedMutation/);
  assert.ok(mutation, "App.applyMutation must remain covered");
  assert.match(mutation[0], /setSelected\(\(old\)\s*=>\s*selectionAfterMutation\(old, selection, result\.notes\.length, result\.changed\)/);
  assert.deepEqual(retainValidSelection([0, 1.5, 2, 3, NaN], 3), [0, 2]);
});


test("no-op mutations preserve selection while successful edits honor explicit selection", () => {
  const current = [1, 3];
  // Duplicate with no room, empty clipboard paste, or unavailable Undo/Redo.
  assert.strictEqual(selectionAfterMutation(current, [], 5, false), current);
  assert.strictEqual(selectionAfterMutation(current, [0], 5, false), current);
  // Even a no-op must discard indices that no longer exist.
  assert.deepEqual(selectionAfterMutation([0, 4, 7], [], 5, false), [0, 4]);
  assert.deepEqual(selectionAfterMutation(current, [], 5, true), []);
  assert.deepEqual(selectionAfterMutation(current, [0, 1.5, 2, 3, NaN], 3, true), [0, 2]);
  assert.strictEqual(selectionAfterMutation(current, undefined, 5, true), current);
});
