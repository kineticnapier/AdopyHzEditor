import assert from "node:assert/strict";
import test from "node:test";
import { clampPitchViewChange } from "../src/editor/pitchViewport.ts";
import type { ViewState } from "../src/editor/bridge.ts";

const view: ViewState = {
  mode: "both", start: 0, windowSeconds: 12, pitchBottom: 40, visibleNotes: 60,
};

test("direct lower-pitch input cannot extend the canvas beyond MIDI 127", () => {
  assert.deepEqual(clampPitchViewChange(view, { pitchBottom: 120 }), { pitchBottom: 68 });
  assert.deepEqual(clampPitchViewChange(view, { pitchBottom: -20 }), { pitchBottom: 0 });
  assert.deepEqual(clampPitchViewChange(view, { pitchBottom: 127, visibleNotes: 6 }), { pitchBottom: 122, visibleNotes: 6 });
});

test("changing pitch span also adjusts the lower bound", () => {
  assert.deepEqual(clampPitchViewChange(view, { visibleNotes: 128 }), { pitchBottom: 0, visibleNotes: 128 });
  assert.deepEqual(clampPitchViewChange(view, { visibleNotes: 200 }), { pitchBottom: 0, visibleNotes: 128 });
  assert.deepEqual(clampPitchViewChange(view, { visibleNotes: 2 }), { pitchBottom: 40, visibleNotes: 6 });
});

test("non-pitch changes preserve their original payload", () => {
  const change = { start: 3, windowSeconds: 6 };
  assert.equal(clampPitchViewChange(view, change), change);
});
