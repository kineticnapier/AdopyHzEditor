import assert from "node:assert/strict";
import test from "node:test";
import { retainValidSelection } from "../src/editor/selectionValidity.ts";

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
