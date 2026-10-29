import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { LatestRequestGate } from "../src/api/requestCoordinator.ts";
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

test("late Track range lookup cannot overwrite a newer selection", async () => {
  const gate = new LatestRequestGate();
  const ticket = gate.issue();
  let release!: (ids: number[]) => void;
  const response = new Promise<number[]>((resolve) => { release = resolve; });
  let selected = [4];
  const pending = response.then((ids) => {
    if (gate.isCurrent(ticket)) selected = ids;
  });
  gate.invalidate(); // Document replacement, source change, or manual selection.
  release([99]);
  await pending;
  assert.deepEqual(selected, [4]);
});

test("Track range lookup has document and selection guards at both ends", () => {
  const app = readFileSync(new URL("../src/App.tsx", import.meta.url), "utf8");
  const canvas = readFileSync(new URL("../src/editor/EditorCanvas.tsx", import.meta.url), "utf8");
  assert.match(app, /const trackSelectionRequests = useRef\(new LatestRequestGate\(\)\)/);
  assert.match(app, /const request = trackSelectionRequests\.current\.issue\(\)/);
  assert.match(app, /generation === documentGeneration\.current/);
  assert.match(app, /trackSelectionRequests\.current\.isCurrent\(request\)/);
  assert.match(app, /if \(!isCurrent\(\)\) return null;/);
  assert.match(canvas, /onFindTracks\(range: TrackSelectionRange\): Promise<number\[\] \| null>/);
  assert.match(canvas, /if\(ids===null\)return;/);
});
