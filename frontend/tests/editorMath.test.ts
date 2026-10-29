import assert from "node:assert/strict";
import test from "node:test";
import { adjacentNoteIndex, boundedGridRange, buildNoteTimeIndex, buildSegmentSpatialIndex, nearbySegmentIndices, noteCandidatesAt, notesInTimeRange, noteEdgeAt, contextMenuDeleteIndices, noteIntersects, noteMidiAt, spectrogramPitchCrop, spectrogramTimeCrop } from "../src/editor/editorMath.ts";

const curve = { start: 0, end: 100, midi: 0, velocity: 100, kind: "curve" as const, midi_end: 0, ctrl1_midi: 127, ctrl2_midi: 127 };

test("narrow curve range selection uses the exact local curve range", () => {
  assert.equal(noteIntersects(curve, .1, .2, .3, .8), true);
});

test("legacy interpolation aliases match canonical modes", () => {
  const note = { ...curve, midi: 60, midi_end: 72, ctrl1_midi: 64, ctrl2_midi: 68 };
  assert.equal(noteMidiAt({ ...note, interpolation: "linear_midi" }, .25), noteMidiAt({ ...note, interpolation: "linear_pitch" }, .25));
  assert.equal(noteMidiAt({ ...note, interpolation: "pitch-linear" }, .25), noteMidiAt({ ...note, interpolation: "linear_pitch" }, .25));
  assert.equal(noteMidiAt({ ...note, interpolation: "hz_linear" }, .25), noteMidiAt({ ...note, interpolation: "linear_hz" }, .25));
});

test("spectrogram crop honors sub-semitone pitch steps", () => {
  const crop = spectrogramPitchCrop(8, 60, .25, 60, 61);
  assert.equal(crop.sy, 3.5);
  assert.equal(crop.sh, 4);
});

test("CQT stale viewport crop keeps absolute time position while scrolling right", () => {
  const crop = spectrogramTimeCrop(0, 12, .96, 12, 1200, 1200);
  assert.ok(crop);
  assert.equal(crop.sx, 96);
  assert.equal(crop.sw, 1104);
  assert.equal(crop.dx, 0);
  assert.equal(crop.dw, 1104);
});

test("CQT stale viewport crop leaves the uncovered left edge blank while scrolling left", () => {
  const crop = spectrogramTimeCrop(.96, 12.96, 0, 12, 1200, 1200);
  assert.ok(crop);
  assert.equal(crop.sx, 0);
  assert.equal(crop.sw, 1104);
  assert.equal(crop.dx, 96);
  assert.equal(crop.dw, 1104);
});

test("CQT stale viewport crop returns null when time ranges do not overlap", () => {
  assert.equal(spectrogramTimeCrop(0, 12, 12.1, 12, 1200, 1200), null);
});

test("CQT viewport zoom maps the overlapping source interval to the correct destination width", () => {
  const zoomIn = spectrogramTimeCrop(0, 12, 3, 6, 1200, 1200);
  assert.deepEqual(zoomIn, { sx: 300, sw: 600, dx: 0, dw: 1200 });
  const zoomOut = spectrogramTimeCrop(0, 12, 0, 24, 1200, 1200);
  assert.deepEqual(zoomOut, { sx: 0, sw: 1200, dx: 0, dw: 600 });
});

test("grid rendering is bounded for extreme BPM and zoom", () => {
  const range = boundedGridRange(0, 3600, 60 / 999999, 0);
  assert.ok(range.count <= 2000);
  assert.ok(range.stride > 1);
});

test("time index excludes notes outside the pointer time", () => {
  const notes = Array.from({length:1000},(_,i)=>({start:i,end:i+.25,midi:60,velocity:100}));
  const candidates=noteCandidatesAt(buildNoteTimeIndex(notes),500.1);
  assert.deepEqual(candidates,[500]);
});

test("time range index returns only notes intersecting the viewport", () => {
  const notes = [
    { start: 0, end: 1, midi: 60, velocity: 100 },
    { start: 2, end: 4, midi: 61, velocity: 100 },
    { start: 8, end: 9, midi: 62, velocity: 100 },
  ];
  assert.deepEqual(notesInTimeRange(buildNoteTimeIndex(notes), 3, 5), [1]);
});

test("track spatial index keeps long, crossing, and point segments discoverable", () => {
  const segments = [
    { ax: 0, ay: 0, bx: 100, by: 100 },
    { ax: 0, ay: 100, bx: 100, by: 0 },
    { ax: 150, ay: 50, bx: 150, by: 50 },
  ];
  const index = buildSegmentSpatialIndex(segments, 24, 8);
  assert.deepEqual(new Set(nearbySegmentIndices(index, 50, 50)), new Set([0, 1]));
  assert.deepEqual(nearbySegmentIndices(index, 150, 50), [2]);
  assert.deepEqual(nearbySegmentIndices(index, 250, 250), []);
});

test("keyboard note navigation follows time order and clamps at both ends", () => {
  const order = [2, 0, 1];
  assert.equal(adjacentNoteIndex(order, null, 1), 2);
  assert.equal(adjacentNoteIndex(order, null, -1), 1);
  assert.equal(adjacentNoteIndex(order, 2, 1), 0);
  assert.equal(adjacentNoteIndex(order, 1, 1), 1);
  assert.equal(adjacentNoteIndex(order, 2, -1), 2);
});

test("short notes prioritize move instead of making their whole width a resize handle", () => {
  assert.equal(noteEdgeAt(100, 116, 100), null);
  assert.equal(noteEdgeAt(100, 115, 107.5), null);
});

test("long notes retain distinct resize handles", () => {
  assert.equal(noteEdgeAt(100, 140, 104), "start");
  assert.equal(noteEdgeAt(100, 140, 136), "end");
  assert.equal(noteEdgeAt(100, 140, 120), null);
});

test("context menu deletes only the pointed note, never the full selection", () => {
  const selection = [0, 2, 4];
  assert.deepEqual(contextMenuDeleteIndices(2), [2]);
  assert.deepEqual(contextMenuDeleteIndices(3), [3]);
  assert.deepEqual(contextMenuDeleteIndices(null), []);
  assert.deepEqual(selection, [0, 2, 4]);
});
