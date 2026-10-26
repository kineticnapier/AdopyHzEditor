import assert from "node:assert/strict";
import test from "node:test";
import { noteIntersects, noteMidiAt, spectrogramPitchCrop } from "../src/editor/editorMath.ts";

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
