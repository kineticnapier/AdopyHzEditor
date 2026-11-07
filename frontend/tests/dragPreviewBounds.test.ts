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

test("canvas ghost preview uses bounded drag helper instead of unbounded argument spreads", () => {
  const source = readFileSync(new URL("../src/editor/EditorCanvas.tsx", import.meta.url), "utf8");
  assert.match(source, /clampDraggedNoteOffset\(props\.notes,\s*drag\.indices,\s*dx,\s*dy,\s*props\.playback\.duration\)/);
  assert.doesNotMatch(source, /Math\.(?:min|max)\(\.\.\.dragged/);
});
