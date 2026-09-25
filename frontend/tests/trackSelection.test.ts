import assert from "node:assert/strict";
import test from "node:test";
import {
  mergeTrackSelection,
  normalizeTrackRange,
  updateTrackSelection,
} from "../src/editor/trackSelection.ts";

test("single track click replaces the selection and ctrl-click toggles", () => {
  assert.deepEqual(updateTrackSelection([1, 2], 7, false), [7]);
  assert.deepEqual(updateTrackSelection([1, 2], 2, true), [1]);
  assert.deepEqual(updateTrackSelection([1, 2], 7, true), [1, 2, 7]);
});

test("rectangular track selection can replace or add without duplicates", () => {
  assert.deepEqual(mergeTrackSelection([1, 2], [4, 5], false), [4, 5]);
  assert.deepEqual(mergeTrackSelection([1, 2], [2, 4], true), [1, 2, 4]);
});

test("track selection ranges are normalized in time and pitch", () => {
  assert.deepEqual(normalizeTrackRange(5, 2, 80, 40), {
    startTime: 2,
    endTime: 5,
    minMidi: 40,
    maxMidi: 80,
  });
});
