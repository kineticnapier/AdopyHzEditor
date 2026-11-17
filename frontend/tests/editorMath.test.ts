import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { adjacentNoteIndex, boundedGridRange, boundedTimelineTickRange, buildNoteTimeIndex, buildSegmentSpatialIndex, nearbySegmentIndices, noteCandidatesAt, notesInTimeRange, noteEdgeAt, contextMenuDeleteIndices, noteIntersects, noteMidiAt, spectrogramPitchCrop, spectrogramPitchVisibleCrop, spectrogramTimeCrop, directSpectrumVisibleCrop, isValidTrackSample } from "../src/editor/editorMath.ts";


test("Direct Spectrum crop maps time and pitch overlap without stretching", () => {
  const crop = directSpectrumVisibleCrop(0, 12, 60, 72, 3, 6, 62, 6, 1200, 600, 600, 300);
  assert.deepEqual(crop, { sx: 300, sy: 200, sw: 600, sh: 300, dx: 0, dy: 0, dw: 600, dh: 300 });
  const upper = directSpectrumVisibleCrop(0, 12, 60, 72, 3, 6, 68, 8, 1200, 600, 600, 400);
  assert.deepEqual(upper, { sx: 300, sy: 0, sw: 600, sh: 200, dx: 0, dy: 200, dw: 600, dh: 200 });
  assert.equal(directSpectrumVisibleCrop(0, 12, 60, 72, 20, 6, 62, 6, 1200, 600, 600, 300), null);
  assert.equal(directSpectrumVisibleCrop(0, 12, 60, 72, 3, 6, 80, 6, 1200, 600, 600, 300), null);
});

test("Direct Spectrum crop rejects non-finite and overflowing metadata before canvas drawing", () => {
  const valid = [0, 12, 60, 72, 3, 6, 62, 6, 1200, 600, 600, 300] as const;
  for (let index = 0; index < valid.length; index += 1) {
    for (const bad of [NaN, Infinity, -Infinity]) {
      const input: number[] = [...valid];
      input[index] = bad;
      assert.equal(directSpectrumVisibleCrop(...(input as unknown as Parameters<typeof directSpectrumVisibleCrop>)), null, `index ${index} / ${bad}`);
    }
  }
  assert.equal(directSpectrumVisibleCrop(-1e308, 1e308, 60, 72, 0, 12, 62, 6, 1200, 600, 600, 300), null);
  assert.equal(directSpectrumVisibleCrop(0, 12, -1e308, 1e308, 3, 6, 62, 6, 1200, 600, 600, 300), null);
  assert.equal(directSpectrumVisibleCrop(0, 12, 60, 72, 1e308, 1e308, 62, 6, 1200, 600, 600, 300), null);
  assert.equal(directSpectrumVisibleCrop(0, 12, 60, 72, 3, 6, -1e308, 1e308, 1200, 600, 600, 300), null);
  assert.equal(directSpectrumVisibleCrop(0, 12, 60, 72, 3, 6, 62, 6, 0, 600, 600, 300), null);
  assert.equal(directSpectrumVisibleCrop(0, 12, 60, 72, 3, 6, 62, 6, 1200.5, 600, 600, 300), null);
  assert.equal(directSpectrumVisibleCrop(0, 12, 60, 72, 3, 6, 62, 6, 1200, 600, 0, 300), null);
});

test("Direct Spectrum canvas uses validated crop rectangles", () => {
  const source = readFileSync(new URL("../src/editor/EditorCanvas.tsx", import.meta.url), "utf8");
  assert.match(source, /const crop = directSpectrumVisibleCrop\(/);
  assert.match(source, /if \(crop\) \{[\s\S]*?ctx\.drawImage\(directSpectrumCanvas,crop\.sx,crop\.sy,crop\.sw,crop\.sh,crop\.dx,crop\.dy,crop\.dw,crop\.dh\)/);
});

test("Frequency Track samples reject invalid packed float values and durations", () => {
  assert.equal(isValidTrackSample(1, 69, .5, .1), true);
  assert.equal(isValidTrackSample(0, 0, 0, 0), true);
  for (const bad of [NaN, Infinity, -Infinity]) {
    for (let field = 0; field < 4; field += 1) {
      const sample = [1, 69, .5, .1];
      sample[field] = bad;
      assert.equal(isValidTrackSample(...(sample as [number, number, number, number])), false);
    }
  }
  assert.equal(isValidTrackSample(1, 69, .5, -.1), false);
  assert.equal(isValidTrackSample(1, 69, -1, .1), false);
  assert.equal(isValidTrackSample(1, 69, 2, .1), false);
});

test("Frequency Track drawing and hover index ignore invalid samples and broken predecessor links", () => {
  const source = readFileSync(new URL("../src/editor/EditorCanvas.tsx", import.meta.url), "utf8");
  assert.match(source, /if \(!validTrackPoint\(i\)\) continue;/);
  assert.match(source, /const connected = valid && i > 0 && validTrackPoint\(i - 1\)/);
  assert.match(source, /const connected = i > 0 && validTrackPoint\(i - 1\)/);
  assert.match(source, /if\(\(decodedTracks\.flags\[i\]&1\)===0&&i>0&&validTrackPoint\(i-1\)/);
});

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

test("CQT pitch crop clips source and destination together at the upper edge", () => {
  const crop = spectrogramPitchVisibleCrop(8, 60, 1, 64, 70, 600);
  assert.deepEqual(crop, { sy: 0, sh: 3.5, dy: 250, dh: 350 });
});

test("CQT pitch crop clips source and destination together at the lower edge", () => {
  const crop = spectrogramPitchVisibleCrop(8, 60, 1, 55, 62, 700);
  assert.deepEqual(crop, { sy: 5.5, sh: 2.5, dy: 0, dh: 250 });
});

test("CQT pitch crop preserves fractional rows and rejects disjoint ranges", () => {
  const crop = spectrogramPitchVisibleCrop(8, 60, 1, 67.4, 67.6, 600);
  assert.ok(crop);
  assert.ok(Math.abs(crop.sy) < 1e-9);
  assert.ok(Math.abs(crop.sh - .1) < 1e-9);
  assert.ok(Math.abs(crop.dy - 300) < 1e-9);
  assert.ok(Math.abs(crop.dh - 300) < 1e-9);
  assert.equal(spectrogramPitchVisibleCrop(8, 60, 1, 80, 90, 600), null);
  assert.equal(spectrogramPitchVisibleCrop(8, 60, 1, 50, 59.5, 600), null);
  assert.equal(spectrogramPitchVisibleCrop(8, 60, 1, 64, 70, 0), null);
});

test("CQT pitch crop rejects non-finite and overflowing metadata before canvas drawing", () => {
  const valid: [number, number, number, number, number, number] = [8, 60, 1, 64, 70, 600];
  for (let index = 0; index < valid.length; index += 1) {
    for (const bad of [NaN, Infinity, -Infinity]) {
      const input: typeof valid = [...valid];
      input[index] = bad;
      assert.equal(spectrogramPitchVisibleCrop(...input), null, `index ${index} / ${bad}`);
    }
  }
  assert.equal(spectrogramPitchVisibleCrop(8, 60, 1e308, 64, 70, 600), null);
  assert.equal(spectrogramPitchVisibleCrop(8, 1e308, 1e308, 64, 70, 600), null);
  assert.equal(spectrogramPitchVisibleCrop(8, 60, 1, -1e308, 1e308, 600), null);
  assert.equal(spectrogramPitchVisibleCrop(8, 60, Number.MIN_VALUE, 64, 70, 600), null);
  assert.equal(spectrogramPitchVisibleCrop(8.5, 60, 1, 64, 70, 600), null);
  assert.equal(spectrogramPitchVisibleCrop(Number.MAX_SAFE_INTEGER + 1, 60, 1, 64, 70, 600), null);
  assert.deepEqual(spectrogramPitchVisibleCrop(...valid), { sy: 0, sh: 3.5, dy: 250, dh: 350 });
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

test("CQT time crop rejects non-finite and overflowing metadata before canvas drawing", () => {
  const valid: [number, number, number, number, number, number] = [0, 12, 3, 6, 1200, 1200];
  for (let index = 0; index < valid.length; index += 1) {
    for (const bad of [NaN, Infinity, -Infinity]) {
      const input: typeof valid = [...valid];
      input[index] = bad;
      assert.equal(spectrogramTimeCrop(...input), null, `index ${index} / ${bad}`);
    }
  }
  assert.equal(spectrogramTimeCrop(-1e308, 1e308, 0, 12, 1200, 1200), null);
  assert.equal(spectrogramTimeCrop(0, 12, 1e308, 1e308, 1200, 1200), null);
  assert.equal(spectrogramTimeCrop(0, 12, 0, 12, Number.MIN_VALUE, 1200), null);
  assert.deepEqual(spectrogramTimeCrop(...valid), { sx: 300, sw: 600, dx: 0, dw: 1200 });
});

test("grid rendering is bounded for extreme BPM and zoom", () => {
  const range = boundedGridRange(0, 3600, 60 / 999999, 0);
  assert.ok(range.count <= 2000);
  assert.ok(range.stride > 1);
});

test("beat grid retains ordinary ticks and bounds long recordings", () => {
  assert.deepEqual(boundedGridRange(0, 12, 1, 0),
    { first: 0, last: 12, stride: 1, count: 13 });
  const long = boundedGridRange(123.4, 36_000, 1, 0);
  assert.ok(long.count > 0 && long.count <= 2000);
  assert.ok(long.stride > 1);
  assert.ok(long.first + (long.count - 1) * long.stride <= long.last);
});

test("beat grid decimation stays at the same density while panning at a boundary", () => {
  const left = boundedGridRange(0, 3998.9, 1, 0);
  const shifted = boundedGridRange(.5, 3998.9, 1, 0);
  assert.equal(left.stride, 3);
  assert.equal(shifted.stride, left.stride);
  assert.equal(shifted.first, left.first);
  assert.ok(left.count <= 2000 && shifted.count <= 2000);
});

test("timeline decimation stays at the same density while panning at a boundary", () => {
  const left = boundedTimelineTickRange(0, 11989, 10);
  const shifted = boundedTimelineTickRange(5, 11989, 10);
  assert.equal(left.stride, 3);
  assert.equal(shifted.stride, left.stride);
  assert.equal(shifted.first, left.first);
  assert.ok(left.count <= 600 && shifted.count <= 600);
});

test("decimated beat grid stays phase-aligned when the viewport pans", () => {
  const first = boundedGridRange(1, 3998, 1, 0);
  const shifted = boundedGridRange(2, 3998, 1, 0);
  assert.equal(first.stride, 2);
  assert.equal(shifted.stride, 2);
  assert.ok(first.first % first.stride === 0);
  assert.equal(shifted.first, first.first);
  assert.ok(first.count <= 2000 && shifted.count <= 2000);
  assert.ok(first.first + (first.count - 1) * first.stride <= first.last);
  assert.ok(shifted.first + (shifted.count - 1) * shifted.stride <= shifted.last);
  const offset = boundedGridRange(1.25, 3998, 1, .25);
  assert.equal(offset.first, first.first);
  const negative = boundedGridRange(-3, 3998, 1, 0);
  assert.ok(negative.first % negative.stride === 0);
});

test("beat grid rejects unsafe ticks and non-finite intermediate values", () => {
  for (const [start, window, beat, offset] of [
    [1e18, 3600, 1, 0], [0, 12, 0, 0], [0, 12, -1, 0],
    [0, 12, NaN, 0], [0, 12, 1, Infinity],
    [0, 12, Number.MIN_VALUE, 0], [1e308, 1e308, 1, 0],
  ]) {
    assert.equal(boundedGridRange(start, window, beat, offset).count, 0);
  }
});

test("canvas iterates beat ticks by bounded count, not floating-point additions", () => {
  const source = readFileSync(new URL("../src/editor/EditorCanvas.tsx", import.meta.url), "utf8");
  assert.match(source, /for\s*\(let i=0;i<beatGrid\.count;i\+=1\)/);
  assert.doesNotMatch(source, /for\s*\(let k=first;k<=last;k\+=stride\)/);
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

test("track hover index bounds extreme and offscreen segments to the visible canvas", () => {
  const segments = [
    { ax: -1e9, ay: 40, bx: 1e9, by: 40 }, // crosses the viewport
    { ax: 1e9, ay: 40, bx: 1e9 + 1, by: 40 }, // entirely outside
    { ax: NaN, ay: 40, bx: 60, by: 40 },
    { ax: Infinity, ay: 40, bx: 60, by: 40 },
    { ax: -3, ay: 10, bx: -3, by: 10 }, // within pointer tolerance
  ];
  const index = buildSegmentSpatialIndex(segments, 24, 8, { width: 120, height: 80 });
  assert.ok(index.buckets.size <= 48, `unexpected bucket count: ${index.buckets.size}`);
  assert.ok(nearbySegmentIndices(index, 60, 40).includes(0));
  assert.ok(nearbySegmentIndices(index, 0, 10).includes(4));
  assert.ok([...index.buckets.values()].every(indices => indices.every(i => i === 0 || i === 4)));
  assert.deepEqual(nearbySegmentIndices(index, 60, 79), []);
});

test("diagonal Track hover index follows the visible line rather than filling its bounding box", () => {
  const index = buildSegmentSpatialIndex(
    [{ ax: -1e9, ay: -1e9, bx: 1e9, by: 1e9 }],
    24, 8, { width: 4096, height: 2048 },
  );
  assert.ok(index.buckets.size < 1000, `diagonal indexed too many cells: ${index.buckets.size}`);
  assert.ok(nearbySegmentIndices(index, 1000, 1000).includes(0));
  assert.deepEqual(nearbySegmentIndices(index, 1000, 1700), []);
  for (const bucket of index.buckets.values()) assert.equal(bucket.length, new Set(bucket).size);
});

test("clipped diagonal and point Track segments retain near-line and edge hover candidates", () => {
  const index = buildSegmentSpatialIndex([
    { ax: -1e9, ay: -1e9, bx: 1e9, by: 1e9 },
    { ax: -200, ay: 50, bx: 300, by: 50 },
    { ax: 20, ay: 20, bx: 20, by: 20 },
  ], 24, 8, { width: 120, height: 80 });
  for (const [x, y] of [[0, 5], [24, 30], [48, 55], [72, 72]]) {
    assert.ok(nearbySegmentIndices(index, x, y).includes(0), `missing diagonal near ${x},${y}`);
  }
  assert.ok(nearbySegmentIndices(index, 120, 50).includes(1));
  assert.ok(nearbySegmentIndices(index, 20, 20).includes(2));
});

test("track hover index refuses invalid viewport dimensions", () => {
  const segments = [{ ax: -1e9, ay: 40, bx: 1e9, by: 40 }];
  for (const width of [0, NaN, Infinity, -1])
    assert.equal(buildSegmentSpatialIndex(segments, 24, 8, { width, height: 80 }).buckets.size, 0);
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

test("timeline second ticks retain ordinary viewport alignment", () => {
  assert.deepEqual(boundedTimelineTickRange(20, 12, 1), { first: 20, stride: 1, count: 13 });
});

test("timeline second ticks are bounded and aligned for long recordings", () => {
  const range = boundedTimelineTickRange(123.4, 36_000, 10);
  assert.ok(range.count > 0 && range.count <= 600);
  assert.ok(range.stride > 1);
  assert.equal(range.first % range.stride, 0);
});

test("timeline ticks reject invalid and unrepresentable ranges", () => {
  for (const [start, window, step] of [
    [NaN, 12, 1], [0, Infinity, 1], [0, 12, 0], [1e18, 3600, 10],
  ]) assert.equal(boundedTimelineTickRange(start, window, step).count, 0);
});

test("canvas iterates a bounded timeline tick count", () => {
  const source = readFileSync(new URL("../src/editor/EditorCanvas.tsx", import.meta.url), "utf8");
  assert.match(source, /boundedTimelineTickRange\(props\.view\.start,props\.view\.windowSeconds,secStep\)/);
  assert.doesNotMatch(source, /for\s*\(let t=Math\.floor\(props\.view\.start\/secStep\)/);
});
