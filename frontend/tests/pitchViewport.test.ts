import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { clampPitchViewChange, hasEffectiveViewChange, pitchBottomToRevealNote } from "../src/editor/pitchViewport.ts";
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

test("keyboard navigation reveals a note exactly at the exclusive upper pitch edge", () => {
  const local = { ...view, pitchBottom: 60, visibleNotes: 12 };
  assert.equal(pitchBottomToRevealNote(local, 71), null);
  assert.equal(pitchBottomToRevealNote(local, 72), 66);
  assert.equal(pitchBottomToRevealNote(local, 60), null);
  assert.equal(pitchBottomToRevealNote(local, 59), 53);
});

test("keyboard navigation can reach MIDI 127 without overflowing the viewport", () => {
  assert.equal(pitchBottomToRevealNote({ ...view, pitchBottom: 60 }, 127), 68);
  assert.equal(pitchBottomToRevealNote({ ...view, pitchBottom: 68 }, 127), null);
  assert.equal(pitchBottomToRevealNote({ ...view, pitchBottom: 0, visibleNotes: 128 }, 127), null);
  assert.equal(pitchBottomToRevealNote({ ...view, pitchBottom: 12, visibleNotes: 6 }, 0), 0);
});

test("canvas keyboard note navigation uses the shared viewport bound policy", () => {
  const source = readFileSync(new URL("../src/editor/EditorCanvas.tsx", import.meta.url), "utf8");
  assert.match(source, /const nextPitchBottom = pitchBottomToRevealNote\(props\.view, note\.midi\)/);
  assert.match(source, /nextPitchBottom !== null\) changes\.pitchBottom = nextPitchBottom/);
});


test("unchanged or empty viewport actions do not dispatch another update", () => {
  assert.equal(hasEffectiveViewChange(view, {}), false);
  assert.equal(hasEffectiveViewChange(view, { mode: "both" }), false);
  assert.equal(hasEffectiveViewChange(view, { start: 0, windowSeconds: 12 }), false);
  assert.equal(hasEffectiveViewChange(view, { pitchBottom: 40, visibleNotes: 60 }), false);
});

test("clamped pitch inputs that leave the viewport unchanged are ignored", () => {
  const full = { ...view, pitchBottom: 0, visibleNotes: 128 };
  assert.equal(hasEffectiveViewChange(full, clampPitchViewChange(full, { pitchBottom: 30 })), false);
  assert.equal(hasEffectiveViewChange(full, clampPitchViewChange(full, { visibleNotes: 200 })), false);
});

test("real time, mode, and pitch changes still dispatch", () => {
  assert.equal(hasEffectiveViewChange(view, { start: 1 }), true);
  assert.equal(hasEffectiveViewChange(view, { mode: "notes" }), true);
  assert.equal(hasEffectiveViewChange(view, clampPitchViewChange(view, { visibleNotes: 48 })), true);
});

test("App filters no-op view changes before disabling playback follow", () => {
  const source = readFileSync(new URL("../src/App.tsx", import.meta.url), "utf8");
  assert.match(source, /const normalized = clampPitchViewChange\(view, changes\);[\s\S]*?if \(!hasEffectiveViewChange\(view, normalized\)\) return;[\s\S]*?setFollowPlayback\(false\)/);
});
