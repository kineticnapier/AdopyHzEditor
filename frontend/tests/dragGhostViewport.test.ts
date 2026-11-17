import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { noteGhostIntersectsViewport } from "../src/editor/editorMath.ts";

test("ghost viewport culls notes outside the visible time and pitch ranges", () => {
  const note = { start: 1, end: 2, midi: 60 };
  assert.equal(noteGhostIntersectsViewport(note, 3, 4, 50, 70), false);
  assert.equal(noteGhostIntersectsViewport(note, 0, 3, 70, 90), false);
  assert.equal(noteGhostIntersectsViewport(note, 0, 3, 50, 70), true);
  assert.equal(noteGhostIntersectsViewport(note, 2, 3, 50, 70), true);
});

test("ghost viewport retains a curve when its controls reach the visible pitch range", () => {
  const curve = { start: 1, end: 2, midi: 100, midi_end: 100, ctrl1_midi: 65, ctrl2_midi: 110, kind: "curve" as const };
  assert.equal(noteGhostIntersectsViewport(curve, 0, 3, 50, 70), true);
  assert.equal(noteGhostIntersectsViewport({ ...curve, ctrl1_midi: 85 }, 0, 3, 50, 70), false);
});

test("ghost viewport keeps note edges visible at the pitch boundary", () => {
  assert.equal(noteGhostIntersectsViewport({ start: 1, end: 2, midi: 60 }, 0, 3, 60.43, 70), true);
  assert.equal(noteGhostIntersectsViewport({ start: 1, end: 2, midi: 60 }, 0, 3, 60.44, 70), false);
});

test("canvas skips out-of-viewport ghost drawing before allocating canvas state", () => {
  const source = readFileSync(new URL("../src/editor/EditorCanvas.tsx", import.meta.url), "utf8");
  assert.match(source, /if\s*\(!noteGhostIntersectsViewport\(ghost,[\s\S]*?\)\)\s*continue;[\s\S]*?ctx\.save\(\)/);
});
