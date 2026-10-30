import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { LatestRequestGate } from "../src/api/requestCoordinator.ts";
import test from "node:test";
import {
  mergeTrackSelection,
  normalizeTrackRange,
  updateTrackSelection,
} from "../src/editor/trackSelection.ts";
import { resolveTrackLookup } from "../src/editor/trackLookup.ts";

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
  assert.match(app, /return resolveTrackLookup\(/);
  const lookupSource = readFileSync(new URL("../src/editor/trackLookup.ts", import.meta.url), "utf8");
  assert.match(lookupSource, /if \(!isCurrent\(\)\) return null;/);
  assert.match(canvas, /onFindTracks\(range: TrackSelectionRange\): Promise<number\[\] \| null>/);
  assert.match(canvas, /if\(ids===null\)return;/);
});

test("failed Track lookup preserves the previous selection", async () => {
  let selected = [4];
  const messages: string[] = [];
  const ids = await resolveTrackLookup(
    async () => { throw new Error("lookup unavailable"); },
    () => true,
    (message) => messages.push(message),
  );
  if (ids !== null) selected = ids;
  assert.equal(ids, null);
  assert.deepEqual(selected, [4]);
  assert.match(messages[0], /lookup unavailable/);
});

test("successful empty Track lookup still clears a non-additive selection", async () => {
  const messages: string[] = [];
  const ids = await resolveTrackLookup(
    async () => ({ trackIds: [], status: "no tracks" }),
    () => true,
    (message) => messages.push(message),
  );
  assert.deepEqual(ids, []);
  assert.deepEqual(messages, ["no tracks"]);
});

test("stale Track lookup errors neither change selection nor show an obsolete error", async () => {
  const messages: string[] = [];
  const ids = await resolveTrackLookup(
    async () => { throw new Error("stale lookup"); },
    () => false,
    (message) => messages.push(message),
  );
  assert.equal(ids, null);
  assert.deepEqual(messages, []);
});

test("successful current Track lookup returns ids", async () => {
  const ids = await resolveTrackLookup(
    async () => ({ trackIds: [7, 3], status: "ok" }),
    () => true,
    () => {},
  );
  assert.deepEqual(ids, [7, 3]);
});
