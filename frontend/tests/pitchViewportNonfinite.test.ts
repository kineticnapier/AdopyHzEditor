import assert from "node:assert/strict";
import test from "node:test";
import {
  clampPitchViewChange,
  hasEffectiveViewChange,
  pitchBottomToRevealNote,
} from "../src/editor/pitchViewport.ts";
import type { ViewState } from "../src/editor/bridge.ts";

const view: ViewState = {
  mode: "both",
  start: 0,
  windowSeconds: 12,
  pitchBottom: 40,
  visibleNotes: 60,
};

test("invalid pitch viewport values cannot enter optimistic state", () => {
  const invalidVisible = clampPitchViewChange(view, { visibleNotes: Number.NaN });
  assert.deepEqual(invalidVisible, { visibleNotes: 60, pitchBottom: 40 });
  assert.equal(hasEffectiveViewChange(view, invalidVisible), false);

  const invalidBottom = clampPitchViewChange(view, { pitchBottom: Number.NEGATIVE_INFINITY });
  assert.deepEqual(invalidBottom, { pitchBottom: 40 });
  assert.equal(hasEffectiveViewChange(view, invalidBottom), false);

  const bothInvalid = clampPitchViewChange(view, {
    visibleNotes: Number.POSITIVE_INFINITY,
    pitchBottom: Number.NaN,
  });
  assert.equal(hasEffectiveViewChange(view, bothInvalid), false);
});

test("invalid pitch field does not discard another valid pitch change", () => {
  assert.deepEqual(
    clampPitchViewChange(view, { visibleNotes: Number.NaN, pitchBottom: 41.5 }),
    { visibleNotes: 60, pitchBottom: 42 },
  );
  assert.deepEqual(
    clampPitchViewChange(view, { visibleNotes: 61.5, pitchBottom: Number.NaN }),
    { visibleNotes: 62, pitchBottom: 40 },
  );
});

test("invalid note pitches do not request a viewport jump", () => {
  assert.equal(pitchBottomToRevealNote(view, Number.NaN), null);
  assert.equal(pitchBottomToRevealNote(view, Number.POSITIVE_INFINITY), null);
  assert.equal(pitchBottomToRevealNote(view, Number.NEGATIVE_INFINITY), null);
  assert.equal(pitchBottomToRevealNote(view, 110), 80);
});
