import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { clampDraggedNoteOffset } from "../src/editor/editorMath.ts";

test("drag preview clamps time and pitch using every selected note and curve control", () => {
  const notes = [
    { start: 1, end: 3, midi: 60 },
    { start: 5, end: 8, midi: 65, kind: "curve" as const, midi_end: 72, ctrl1_midi: 2, ctrl2_midi: 125 },
  ];
  assert.deepEqual(clampDraggedNoteOffset(notes, [0, 1], 50, 10, 10), { dx: 2, dy: 2 });
  assert.deepEqual(clampDraggedNoteOffset(notes, [0, 1], -50, -10, 10), { dx: -1, dy: -2 });
  assert.deepEqual(clampDraggedNoteOffset(notes, [999], 4, 3, 10), { dx: 4, dy: 3 });
});

test("drag preview handles 200000 selected notes without spreading arrays into Math.min/max", () => {
  const note = { start: 1, end: 2, midi: 60 };
  const notes = Array(200_000).fill(note);
  const indices = Array.from({ length: notes.length }, (_, index) => index);
  assert.deepEqual(clampDraggedNoteOffset(notes, indices, 100, 100, 10), { dx: 8, dy: 67 });
});

test("snapped drag preview uses the lowest valid note index, not click selection order", () => {
  // Backend _valid_indices sorts indices before using original[0] for snap.
  const notes = [
    { start: 0.3, end: 0.7, midi: 60 },
    { start: 1, end: 1.2, midi: 64 },
  ];
  const snapHalfSecond = (time: number) => Math.round(time * 2) / 2;
  const result = clampDraggedNoteOffset(notes, [1, 0], 0.34, 0, 5, snapHalfSecond);
  assert.ok(Math.abs(result.dx - 0.2) < 1e-9);
  assert.equal(result.dy, 0);
});

test("snapped drag preview clamps raw delta before snapping at the song end", () => {
  // Backend move_notes clamps to duration first, then snaps the first note.
  const notes = [{ start: 1.1, end: 4.9, midi: 60 }];
  const snapHalfSecond = (time: number) => Math.round(time * 2) / 2;
  const result = clampDraggedNoteOffset(notes, [0], 2, 0, 5, snapHalfSecond);
  assert.ok(Math.abs(result.dx + 0.1) < 1e-9);
  assert.equal(result.dy, 0);
});

test("snapped drag preview handles large reversed selections without argument spreading", () => {
  const notes = Array(200_000).fill({ start: 1, end: 2, midi: 60 });
  const indices = Array.from({ length: notes.length }, (_, i) => notes.length - 1 - i);
  assert.deepEqual(clampDraggedNoteOffset(notes, indices, 0.3, 0, 10, t => Math.round(t)), { dx: 0, dy: 0 });
});

test("canvas ghost preview uses bounded drag helper instead of unbounded argument spreads", () => {
  const source = readFileSync(new URL("../src/editor/EditorCanvas.tsx", import.meta.url), "utf8");
  assert.match(source, /clampDraggedNoteOffset\(\s*props\.notes,\s*drag\.indices,\s*rawDx,\s*dy,\s*props\.playback\.duration,/);
  assert.doesNotMatch(source, /Math\.(?:min|max)\(\.\.\.dragged/);
});
